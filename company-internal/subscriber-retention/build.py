"""Build subscriber retention chart + metrics per yousquared_retention_spec.md.

Inputs: events-export*.csv in ~/Downloads (Mixpanel → RevenueCat events).
Outputs:
  assets/retention-chart.svg  — broken-x-axis KM + stabilized-core forecast
  assets/metrics.json         — headline stats for the HTML page
  assets/fallback-users.json  — active users whose revenue had to be imputed
"""

from __future__ import annotations

import glob
import json
import math
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch  # noqa: F401  (kept for future)
from scipy import stats as sstats

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)

DOWNLOADS = Path.home() / "Downloads"
PATTERN = "events-export*.csv"

SEC_PER_DAY = 86400


# ---------- 1. Ingest ----------

def load_events() -> pd.DataFrame:
    files = sorted(glob.glob(str(DOWNLOADS / PATTERN)))
    if not files:
        raise SystemExit(f"No files match {DOWNLOADS}/{PATTERN}")
    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f, low_memory=False))
        except Exception as e:
            print(f"skip {f}: {e}")
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["Event Name", "Time", "Distinct ID"])
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df = df[df["Time"].notna()].copy()
    df["dt"] = pd.to_datetime(df["Time"], unit="s", utc=True)
    print(f"loaded {len(df):,} unique events from {len(files)} files")
    return df


# ---------- 2. Survival ----------

def build_survival(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    max_time = df["Time"].max()
    starts = (
        df[df["Event Name"] == "rc_initial_purchase_event"]
        .groupby("Distinct ID")["Time"].min()
        .rename("start_time")
    )
    cancels = (
        df[df["Event Name"] == "rc_cancellation_event"]
        .groupby("Distinct ID")["Time"].min()
        .rename("cancel_time")
    )
    surv = pd.concat([starts, cancels], axis=1)
    surv = surv[surv["start_time"].notna()].copy()
    surv["observed"] = surv["cancel_time"].notna().astype(int)
    surv["duration_days"] = np.where(
        surv["observed"] == 1,
        (surv["cancel_time"] - surv["start_time"]) / SEC_PER_DAY,
        (max_time - surv["start_time"]) / SEC_PER_DAY,
    )
    surv = surv[surv["duration_days"] >= 0]
    print(f"survival cohort: {len(surv):,} subscribers, {surv['observed'].sum():,} churned")
    return surv, max_time


def kaplan_meier(surv: pd.DataFrame) -> pd.DataFrame:
    durations = surv["duration_days"].values
    observed = surv["observed"].values
    times = np.unique(np.concatenate([[0.0], durations]))
    times = np.sort(times)
    rows = []
    s = 1.0
    for t in times:
        at_risk = int((durations >= t).sum())
        events = int(((durations == t) & (observed == 1)).sum())
        if at_risk == 0:
            break
        if events > 0:
            s = s * (1 - events / at_risk)
        # Beta CI on S(t)
        a = s * at_risk + 1
        b = (1 - s) * at_risk + 1
        lo, hi = sstats.beta.ppf([0.025, 0.975], a, b)
        rows.append({"t_days": t, "at_risk": at_risk, "events": events, "S": s, "lo": lo, "hi": hi})
    km = pd.DataFrame(rows)
    km["lo"] = np.minimum.accumulate(km["lo"].values)
    km["hi"] = np.minimum.accumulate(km["hi"].values)
    return km


# ---------- 3. Stabilized-core forecast ----------

def survival_at_day(km: pd.DataFrame, day: float) -> float:
    mask = km["t_days"] <= day
    if not mask.any():
        return 1.0
    return float(km.loc[mask, "S"].iloc[-1])


def build_forecast(km: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, float, float, int]:
    s2 = survival_at_day(km, 65)
    s8 = survival_at_day(km, 240)
    abs_drop = s2 - s8
    months = np.arange(0, 120 + 0.1, 0.1)
    forecast = np.empty_like(months)
    km_months = km["t_days"].values / 30.0
    km_S = km["S"].values
    for i, m in enumerate(months):
        if m < 8:
            mask = km_months <= m
            forecast[i] = km_S[mask][-1] if mask.any() else 1.0
        else:
            steps = int((m - 8) // 6) + 1
            forecast[i] = max(0.0, s8 - abs_drop * steps)
    zero_idx = np.argmax(forecast <= 0)
    zero_month = float(months[zero_idx]) if forecast[zero_idx] <= 0 else float(months[-1])
    return months, forecast, s2, s8, zero_month


# ---------- 4. Weighted ARPU ----------

PRICE_FALLBACK = 30.0


def infer_price(product_id: str | float, revenue: float | None) -> tuple[float, str]:
    """Return (monthly_revenue, basis_tag). basis_tag ∈ {rev, rev/12, elite, pro, default}."""
    pid = (str(product_id) if pd.notna(product_id) else "").lower()
    if pd.notna(revenue) and revenue and float(revenue) > 0:
        r = float(revenue)
        if "year" in pid or "annual" in pid:
            return r / 12.0, "rev/12"
        return r, "rev"
    if "elite" in pid:
        return 60.0, "elite"
    if "pro" in pid:
        return 30.0, "pro"
    return PRICE_FALLBACK, "default"


def weighted_arpu(df: pd.DataFrame, surv: pd.DataFrame, max_time: float) -> tuple[float, int, list[dict]]:
    max_dt = pd.to_datetime(max_time, unit="s", utc=True)
    current_month_start = pd.Timestamp(year=max_dt.year, month=max_dt.month, day=1, tz="UTC").timestamp()

    active_mask = (surv["start_time"] <= max_time) & (
        surv["cancel_time"].isna() | (surv["cancel_time"] >= current_month_start)
    )
    active_ids = surv.index[active_mask]

    purchase_events = df[df["Event Name"].isin(["rc_initial_purchase_event", "rc_renewal_event"])].copy()
    purchase_events = purchase_events[purchase_events["Distinct ID"].isin(active_ids)]
    purchase_events = purchase_events.sort_values("Time")
    latest = purchase_events.groupby("Distinct ID").tail(1).set_index("Distinct ID")

    total_mrr = 0.0
    fallback_rows = []
    for uid in active_ids:
        if uid in latest.index:
            row = latest.loc[uid]
            pid = row.get("product_id", None)
            rev = row.get("revenue", None)
        else:
            pid, rev = None, None
        price, basis = infer_price(pid, rev)
        total_mrr += price
        if basis in ("elite", "pro", "default"):
            fallback_rows.append({
                "distinct_id": str(uid),
                "product_id": str(pid) if pid is not None else "",
                "revenue_raw": None if pd.isna(rev) else float(rev),
                "imputed_mrr": price,
                "basis": basis,
            })
    n_active = int(active_mask.sum())
    arpu = total_mrr / n_active if n_active else 0.0
    return arpu, n_active, fallback_rows


# ---------- 5. Chart ----------

BRAND = {
    "km": "#4A7BA6",          # blue
    "km_fill": "#B6CFE4",     # light blue
    "forecast": "#8C8680",    # warm grey
    "anchor": "#E07A5F",      # terracotta
    "text": "#2D2A26",        # charcoal
    "muted": "#6B6560",
    "grid": "#EDE8E3",
}


def render_chart(km: pd.DataFrame, months: np.ndarray, forecast: np.ndarray,
                 s2: float, s8: float, abs_drop: float, zero_month: float,
                 arpu: float, lifetime_months: float, ltv: float,
                 surv: pd.DataFrame, out: Path) -> None:
    fig, (axL, axR) = plt.subplots(
        1, 2, sharey=True, figsize=(12.2, 5.4),
        gridspec_kw={"width_ratios": [3, 1.5]},
    )
    plt.subplots_adjust(wspace=0.06, top=0.86, bottom=0.18, left=0.07, right=0.97)

    km_months = km["t_days"].values / 30.0

    for ax in (axL, axR):
        ax.plot(months, forecast, linestyle=(0, (6, 4)), color=BRAND["forecast"], linewidth=2.0,
                label=f"Conservative Forecast (Lifetime: ~{int(round(lifetime_months))} Mo, LTV: ${int(round(ltv)):,})")
        ax.step(km_months, km["S"], where="post", color=BRAND["km"], linewidth=2.4,
                label="Observed Retention (KM model)")
        ax.fill_between(km_months, km["lo"], km["hi"], step="post", color=BRAND["km_fill"], alpha=0.55)
        ax.grid(True, axis="y", linestyle="-", color=BRAND["grid"], linewidth=0.8)
        ax.set_axisbelow(True)

    axL.set_xlim(0, 14)
    axL.set_xticks([0, 2, 4, 6, 8, 10, 12, 14])
    axR.set_xlim(32, 40)
    axR.set_xticks([32, 34, 36, 38, 40])

    axL.set_ylim(0, 1.02)
    axL.set_yticks(np.arange(0, 1.01, 0.2))
    axL.set_yticklabels([f"{int(v*100)}%" for v in np.arange(0, 1.01, 0.2)])

    axL.spines["right"].set_visible(False)
    axR.spines["left"].set_visible(False)
    axR.tick_params(left=False, labelleft=False)
    for ax in (axL, axR):
        ax.spines["top"].set_visible(False)
        ax.spines["bottom"].set_color(BRAND["muted"])
        ax.spines["left"].set_color(BRAND["muted"]) if ax is axL else None
        ax.tick_params(colors=BRAND["muted"])

    # Diagonal break marks
    d = 0.012
    kwargs = dict(transform=axL.transAxes, color=BRAND["muted"], clip_on=False, linewidth=1)
    axL.plot((1 - d, 1 + d), (-d, d), **kwargs)
    axL.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)
    kwargs = dict(transform=axR.transAxes, color=BRAND["muted"], clip_on=False, linewidth=1)
    axR.plot((-d * 2, d * 2), (-d, d), **kwargs)
    axR.plot((-d * 2, d * 2), (1 - d, 1 + d), **kwargs)

    # Sample size annotations on left
    durations = surv["duration_days"].values
    for m in [0, 1, 2, 3, 4, 5, 6, 8]:
        day = m * 30
        n = int((durations >= day).sum())
        s_val = survival_at_day(km, day)
        axL.annotate(f"n={n}", xy=(m, s_val), xytext=(0, 9), textcoords="offset points",
                     ha="center", fontsize=8.5, color=BRAND["muted"], fontweight=500)

    # Title + axis labels
    fig.suptitle("YouSquared subscriber retention: near-zero churn after month 3",
                 fontsize=14, fontweight="bold", color=BRAND["text"], y=0.96)
    fig.text(0.5, 0.12, "Months since Initial Purchase", ha="center",
             fontsize=11, color=BRAND["muted"])
    axL.set_ylabel("Retention Probability", fontsize=10.5, color=BRAND["muted"])

    # Legend: include N proxy blank
    handles, labels = axL.get_legend_handles_labels()
    from matplotlib.lines import Line2D
    proxy = Line2D([0], [0], color="none", label="n = number of users who's stayed subscribed this far")
    handles.append(proxy)
    labels.append(proxy.get_label())
    axL.legend(handles, labels, loc="lower left", frameon=False, fontsize=9.3,
               labelcolor=BRAND["muted"])

    fig.text(0.5, 0.065, "Assume same % drop every 6 months as between month 2 and 8",
             ha="center", fontsize=11, color=BRAND["muted"], style="italic")

    fig.savefig(out, format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------- main ----------

def main() -> None:
    df = load_events()
    surv, max_time = build_survival(df)
    km = kaplan_meier(surv)
    months, forecast, s2, s8, zero_month = build_forecast(km)
    abs_drop = s2 - s8

    arpu, n_active, fallback_rows = weighted_arpu(df, surv, max_time)
    lifetime_months = float(forecast.sum() * 0.1)
    ltv = arpu * lifetime_months

    # Net monthly churn implied by stabilized drop
    monthly_drop_stable = abs_drop / 6.0  # percentage points per month post-month-8

    out_chart = ASSETS / "retention-chart.svg"
    render_chart(km, months, forecast, s2, s8, abs_drop, zero_month, arpu,
                 lifetime_months, ltv, surv, out_chart)

    metrics = {
        "as_of": pd.to_datetime(max_time, unit="s", utc=True).strftime("%Y-%m-%d"),
        "total_subscribers": int(len(surv)),
        "total_churned": int(surv["observed"].sum()),
        "active_subscribers": n_active,
        "weighted_arpu_usd": round(arpu, 2),
        "lifetime_months": round(lifetime_months, 1),
        "ltv_usd": round(ltv),
        "s_month2": round(s2, 4),
        "s_month8": round(s8, 4),
        "abs_drop_pp": round(abs_drop * 100, 2),
        "monthly_drop_post_stabilization_pp": round(monthly_drop_stable * 100, 3),
        "zero_month": round(zero_month, 1),
        "fallback_count": len(fallback_rows),
    }
    (ASSETS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (ASSETS / "fallback-users.json").write_text(json.dumps(fallback_rows, indent=2))

    print(json.dumps(metrics, indent=2))
    print(f"\nImputed-revenue users (count by basis):")
    from collections import Counter
    print(Counter(r["basis"] for r in fallback_rows))


if __name__ == "__main__":
    main()
