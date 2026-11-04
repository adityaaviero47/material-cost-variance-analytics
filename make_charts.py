"""Charts for README from results/results.json."""
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = json.load(open("results/results.json"))
B = R["bridge"]; yrs = [b["year"] for b in B]
fig, ax = plt.subplots(2, 2, figsize=(11.5, 7.6))
pv = [b["price_variance"] / 1e6 for b in B]; uv = [b["usage_variance"] / 1e6 for b in B]
x = range(len(yrs))
ax[0, 0].bar([i - .2 for i in x], uv, .4, color="#9AA5AD", label="Usage variance")
ax[0, 0].bar([i + .2 for i in x], pv, .4, color="#0052CC", label="Price variance")
ax[0, 0].axhline(0, color="#555", lw=.8); ax[0, 0].set_xticks(list(x)); ax[0, 0].set_xticklabels(yrs)
ax[0, 0].set_ylabel("USD million vs prior year"); ax[0, 0].legend(fontsize=8)
ax[0, 0].set_title("Spend bridge: volume drove the rise, price pulled it down")

ax[0, 1].plot([2007] + yrs, [100] + [b["price_index"] for b in B], "o-", color="#0052CC")
for yv, b in zip(yrs[-1:], B[-1:]): ax[0, 1].text(yv, b["price_index"] + 4, f"{b['price_index']:.0f}", ha="center")
ax[0, 1].set_ylim(0, 110); ax[0, 1].set_ylabel("Same-item price index (2007 = 100)")
ax[0, 1].set_title("Same-item prices fell 56% over 2007-2015")

t = R["top_adverse"]; tot = t["total_adverse_pv"]; cum = 0; cs = []
for r in t["top10"]: cum += r["adverse_pv"]; cs.append(cum / tot * 100)
ax[1, 0].bar(range(1, 11), [r["adverse_pv"] / 1e6 for r in t["top10"]], color="#E07A2F")
a2 = ax[1, 0].twinx(); a2.plot(range(1, 11), cs, "o-", color="#0052CC"); a2.set_ylim(0, 100); a2.set_ylabel("Cumulative share (%)")
a2.spines[["top"]].set_visible(False)
ax[1, 0].set_xticks(range(1, 11)); ax[1, 0].set_xlabel("Material rank by adverse price variance"); ax[1, 0].set_ylabel("USD million")
ax[1, 0].set_title(f"Top 10 of {t['items_with_adverse_pv']} materials: {t['top10_share']*100:.0f}% of adverse variance")

fm = {r["Shipment Mode"]: r for r in R["freight_by_mode"]}
modes = ["Truck", "Ocean", "Air Charter", "Air"]
ax[1, 1].bar(modes, [fm[m]["usd_per_kg"] for m in modes], color=["#9AA5AD", "#9AA5AD", "#9AA5AD", "#E07A2F"])
for i, m in enumerate(modes): ax[1, 1].text(i, fm[m]["usd_per_kg"] + .1, f"${fm[m]['usd_per_kg']:.2f}", ha="center")
ax[1, 1].set_ylabel("Freight cost (USD per kg)"); ax[1, 1].set_title("Freight: air costs 2.8x ocean per kg")
for a in ax.flat: a.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig("results/summary.png", dpi=150)
