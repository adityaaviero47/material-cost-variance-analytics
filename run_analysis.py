"""Material cost variance analytics on real procurement data (USAID SCMS delivery history, 2006-2015).
Validates the raw upload, splits each year's change in material spend into price and usage variance,
finds the top adverse materials, and checks root causes (vendor, fulfilment route, shipment mode).
Reproduces every number in README.md:  python run_analysis.py"""
import json, numpy as np, pandas as pd

R = {}
raw = pd.read_csv("data/SCMS_Delivery_History_Dataset.csv.gz")
fix = lambda s: s.encode("latin1").decode("utf8") if isinstance(s, str) and "Ã" in s else s
raw["Country"] = raw["Country"].map(fix)

# ---------- 1. validate the upload (the checks a governed Excel upload would run) ----------
d = raw.copy()
d["date"] = pd.to_datetime(d["Scheduled Delivery Date"], format="%d-%b-%y", errors="coerce")
d["freight"] = pd.to_numeric(d["Freight Cost (USD)"], errors="coerce")
d["weight"] = pd.to_numeric(d["Weight (Kilograms)"], errors="coerce")
mismatch = (d["Line Item Quantity"] * d["Pack Price"] - d["Line Item Value"]).abs() > 0.01 * d["Line Item Value"].clip(lower=1)
checks = {
    "rows": len(d),
    "bad_or_missing_date": int(d.date.isna().sum()),
    "zero_value_lines": int((d["Line Item Value"] <= 0).sum()),
    "zero_quantity_lines": int((d["Line Item Quantity"] <= 0).sum()),
    "value_not_equal_qty_x_price": int(mismatch.sum()),
    "duplicate_ids": int(d["ID"].duplicated().sum()),
    "freight_not_numeric": int(d.freight.isna().sum()),
    "freight_included_in_commodity_cost": int(raw["Freight Cost (USD)"].astype(str).str.startswith("Freight Included").sum()),
    "freight_on_other_line": int(raw["Freight Cost (USD)"].astype(str).str.startswith("See").sum()),
}
d = d[(d["Line Item Value"] > 0) & (d["Line Item Quantity"] > 0) & d.date.notna() & ~mismatch]
checks["rows_passed"] = len(d)
R["validation"] = checks
d["year"] = d.date.dt.year
d["item"] = d["Item Description"]
R["data"] = dict(lines=int(len(d)), items=int(d.item.nunique()), vendors=int(d.Vendor.nunique()), countries=int(d.Country.nunique()),
                 spend_usd=float(d["Line Item Value"].sum()), start=str(d.date.min().date()), end=str(d.date.max().date()))

# ---------- 2. price vs usage variance, year on year ----------
# For item i in year t: AQ = actual quantity (packs), AP = actual average pack price = value / AQ,
# SP = standard price = item's average pack price in year t-1, BQ = baseline quantity = item's quantity in t-1.
# Price variance PV = (AP - SP) x AQ ; usage variance UV = (AQ - BQ) x SP. PV + UV = AQ x AP - BQ x SP.
y = d.groupby(["item", "year"]).agg(q=("Line Item Quantity", "sum"), v=("Line Item Value", "sum")).reset_index()
y["p"] = y.v / y.q
prev = y.assign(year=y.year + 1).rename(columns={"q": "bq", "v": "bv", "p": "sp"})
m = y.merge(prev[["item", "year", "bq", "bv", "sp"]], on=["item", "year"], how="outer")
m = m[(m.year >= 2008) & (m.year <= 2015)].copy()
both = m.dropna(subset=["q", "bq"]).copy()
both["PV"] = (both.p - both.sp) * both.q
both["UV"] = (both.q - both.bq) * both.sp
rows = []
for t in range(2008, 2016):
    b = both[both.year == t]; mt = m[m.year == t]
    rows.append(dict(year=t, spend=float(mt.v.sum()), prior_spend=float(mt.bv.sum()),
                     price_variance=float(b.PV.sum()), usage_variance=float(b.UV.sum()),
                     new_items=float(mt[mt.bq.isna()].v.sum()), dropped_items=-float(mt[mt.q.isna()].bv.sum()),
                     price_change_continuing=float(b.v.sum() / (b.sp * b.q).sum() - 1)))
B = pd.DataFrame(rows)
B["check"] = B.prior_spend + B.price_variance + B.usage_variance + B.new_items + B.dropped_items - B.spend
assert B.check.abs().max() < 1, "bridge does not reconcile"
B["price_index"] = 100 * (1 + B.price_change_continuing).cumprod()     # 2007 = 100, same-item prices chained
R["bridge"] = B.drop(columns="check").round(4).to_dict("records")
R["totals"] = dict(price_variance=float(B.price_variance.sum()), usage_variance=float(B.usage_variance.sum()),
                   price_index_2015=float(B.price_index.iloc[-1]),
                   spend_growth_2008_2015=float(B.spend.iloc[-1] / B.spend.iloc[0] - 1))

# ---------- 3. top adverse materials (Pareto of adverse price variance) ----------
adv = both[both.PV > 0].groupby("item").PV.sum().sort_values(ascending=False)
R["top_adverse"] = dict(items_with_adverse_pv=int(len(adv)), total_adverse_pv=float(adv.sum()),
                        top10_share=float(adv.head(10).sum() / adv.sum()), top5_share=float(adv.head(5).sum() / adv.sum()),
                        top10=[dict(item=i, adverse_pv=float(v)) for i, v in adv.head(10).items()])
fav = both[both.PV < 0].PV.sum()
R["top_adverse"]["total_favourable_pv"] = float(fav)

# ---------- 4. root causes ----------
# (a) vendor price spread: same item, same year, lines paying above that item-year's median pack price
d["med"] = d.groupby(["item", "year"])["Pack Price"].transform("median")
d["above"] = (d["Pack Price"] - d.med).clip(lower=0) * d["Line Item Quantity"]
multi = d.groupby(["item", "year"]).Vendor.transform("nunique") > 1
R["root_cause"] = dict(
    spend_above_item_year_median=float(d.above.sum()), share_of_spend=float(d.above.sum() / d["Line Item Value"].sum()),
    above_median_from_multi_vendor_items=float(d.above[multi].sum() / d.above.sum()))
by_v = d.groupby("Vendor").above.sum().sort_values(ascending=False)
R["root_cause"]["top3_vendors_share_of_above_median"] = float(by_v.head(3).sum() / by_v.sum())
R["root_cause"]["top_vendors"] = [dict(vendor=k, usd=float(v)) for k, v in by_v.head(5).items()]
# (b) fulfilment route: same item and year bought both from the regional distribution centre and as a direct drop
g = d.groupby(["item", "year", "Fulfill Via"]).agg(q=("Line Item Quantity", "sum"), v=("Line Item Value", "sum")).reset_index()
g["p"] = g.v / g.q
w = g.pivot_table(index=["item", "year"], columns="Fulfill Via", values=["p", "q"]).dropna()
rdc_vs_dd = float((w["p"]["From RDC"] * w["q"]["From RDC"]).sum() / (w["p"]["Direct Drop"] * w["q"]["From RDC"]).sum() - 1)
R["root_cause"]["rdc_price_vs_direct_drop_same_item_year"] = rdc_vs_dd
R["root_cause"]["item_years_with_both_routes"] = int(len(w))
# (c) freight: cost as a share of goods value and per kg, by shipment mode (lines with a numeric freight cost)
f = d[d.freight.notna() & d.weight.notna() & (d.weight > 0)]
fm = f.groupby("Shipment Mode").agg(lines=("ID", "size"), freight=("freight", "sum"), value=("Line Item Value", "sum"), kg=("weight", "sum"))
fm["freight_pct_of_value"] = fm.freight / fm.value; fm["usd_per_kg"] = fm.freight / fm.kg
R["freight_by_mode"] = fm.round(4).reset_index().to_dict("records")
air = fm.loc["Air"]; ocean = fm.loc["Ocean"]; truck = fm.loc["Truck"]
R["freight_summary"] = dict(air_per_kg=float(air.usd_per_kg), ocean_per_kg=float(ocean.usd_per_kg), truck_per_kg=float(truck.usd_per_kg),
                            air_vs_ocean_per_kg=float(air.usd_per_kg / ocean.usd_per_kg),
                            air_share_of_freight=float(fm.freight.get("Air", 0) / fm.freight.sum()),
                            freight_pct_of_value_all=float(fm.freight.sum() / fm.value.sum()))

# ---------- 5. monthly spend series ----------
mo = d.groupby(d.date.dt.to_period("M"))["Line Item Value"].sum()
R["monthly"] = dict(months=int(len(mo)), peak_month=str(mo.idxmax()), peak_spend=float(mo.max()))
mo.rename("spend").to_csv("results/monthly_spend.csv")

# ---------- dashboard workbook ----------
with pd.ExcelWriter("results/variance_dashboard.xlsx") as x:
    pd.DataFrame(list(checks.items()), columns=["check", "count"]).to_excel(x, "Validation", index=False)
    B.drop(columns="check").to_excel(x, "Yearly bridge", index=False)
    adv.head(25).rename("adverse_price_variance_usd").to_frame().to_excel(x, "Top adverse items")
    both.sort_values("PV", ascending=False)[["item", "year", "bq", "q", "sp", "p", "PV", "UV"]].to_excel(x, "Item-year variance", index=False)
    by_v.rename("spend_above_median_usd").to_frame().to_excel(x, "Vendor spread")
    fm.to_excel(x, "Freight by mode")
json.dump(R, open("results/results.json", "w"), indent=2, default=str)
print(json.dumps(R, indent=2, default=str))
