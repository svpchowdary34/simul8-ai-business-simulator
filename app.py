# SIMUL8 AI — What-If Business Simulator | ONE Google Colab cell
# Test the decision. Before you make it.
import subprocess, sys, os, re, zipfile, html, math, datetime, warnings
warnings.filterwarnings("ignore")
try:
    import gradio, plotly
    assert int(gradio.__version__.split(".")[0]) in (4, 5)
except Exception:
    subprocess.call([sys.executable, "-m", "pip", "install", "-q", "gradio>=4.44,<6", "plotly", "pandas", "numpy"])
import numpy as np, pandas as pd, plotly.graph_objects as go, gradio as gr

C = dict(fg="#193B37", sg="#BCE8B0", am="#E8B96A", iv="#F5F2E9", ch="#263B37", li="#D6C8F0", co="#D98276", gg="#A5B5AD")
G = {}; TESTS = []; INF = float("inf"); RN = ["Workforce", "Production", "Inventory", "Logistics"]
esc = lambda x: html.escape(str(x)); nul = lambda v: v is None or (not isinstance(v, str) and bool(pd.isna(v)))
nf = lambda v: "—" if nul(v) else ("∞" if np.isinf(v) else format(v, ",.0f"))
pc = lambda v, d=0: "—" if nul(v) else ("∞" if np.isinf(v) else format(v, ".%d%%" % d))
sg = lambda v: "—" if nul(v) or np.isinf(v) else "%+.1f%%" % (100 * v)
def money(v):
    if nul(v) or np.isinf(v): return "—"
    a = abs(v); s = "-" if v < 0 else ""
    return s + "₹" + (format(a / 1e7, ".2f") + "Cr" if a >= 1e7 else format(a / 1e5, ".1f") + "L" if a >= 1e5 else format(a, ",.0f"))
def note(t, k="info"): return "<div class='note' style='border-left:4px solid %s'>%s</div>" % ({"info": C["gg"], "ok": C["fg"], "warn": C["am"], "err": C["co"], "ai": C["li"]}[k], t)
def card(l, v, d, c=C["fg"]): return "<div class='kc'><div class='kl'>%s</div><div class='kv' style='color:%s'>%s</div><div class='kd'>%s</div></div>" % (l, c, v, d)
SEC = lambda t: "<div class='sec'>%s</div>" % t
def trows(h, rows):
    s = "<div class='tw'><table><tr>" + "".join("<th>%s</th>" % x for x in h) + "</tr>"
    for r in rows: s += "<tr>" + "".join("<td>%s</td>" % x for x in r) + "</tr>"
    return s + "</table></div>"
def sty(f, h=340, t=""):
    f.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=C["ch"]), height=h, title=dict(text=t, x=.02), margin=dict(l=55, r=25, t=50, b=45), legend=dict(orientation="h", y=-.25), colorway=[C["fg"], C["am"], C["li"], C["co"], C["gg"]]); return f
VC = {"Feasible with current capacity": ("✓", C["sg"]), "Feasible with targeted investment": ("◆", C["li"]), "Not feasible under current assumptions": ("▲", C["co"])}
def vpill(v): i, c = VC[v]; return "<span class='pill' style='background:%s'>%s %s</span>" % (c, i, v)
def banner(): return note("<b>Illustrative synthetic data.</b> Fictional home-appliance maker; every result is a model-based estimate under stated assumptions, not observed performance.", "warn") if G.get("demo") else note("Using your uploaded data. Results are model-based estimates under stated assumptions.", "info")

# ------------------------------ FICTIONAL synthetic business (fixed seed) ------------------------------
PROD = [("Pressure Cooker 3L", 3800, 1650, .35, .22), ("Mixer Grinder 750W", 2600, 3400, .55, .40), ("Induction Cooktop", 2100, 2300, .45, .30), ("Air Fryer 4L", 1500, 5200, .75, .55), ("Water Heater 15L", 1100, 6800, .95, .70), ("Ceiling Fan 1200mm", 1000, 2900, .60, .35)]
PCOLS = ["product", "monthly_units", "unit_price", "unit_variable_cost", "labour_h_per_unit", "machine_h_per_unit"]
RCOLS = ["employees", "productive_hours_per_employee_month", "productivity_index", "machine_lines", "shifts_per_day", "machine_hours_per_line_shift_month", "fleet_vehicles", "units_per_vehicle_month", "raw_material_stock_units", "replenishment_units_month", "finished_goods_units", "fixed_costs_month"]
def make_data(seed=8):
    r = np.random.default_rng(seed); pr = pd.DataFrame([dict(product=n, monthly_units=u, unit_price=p, unit_variable_cost=round(p * float(r.uniform(.60, .68))), labour_h_per_unit=l, machine_h_per_unit=m) for n, u, p, l, m in PROD]); D0 = pr.monthly_units.sum()
    lh = (pr.monthly_units * pr.labour_h_per_unit).sum() / D0; mh = (pr.monthly_units * pr.machine_h_per_unit).sum() / D0; hrs, sh, mls = 147.0, 2, 176.0
    rs = dict(employees=int(round(D0 * lh / (hrs * .935))), productive_hours_per_employee_month=hrs, productivity_index=1.0, machine_lines=int(round(D0 * mh / (sh * mls * .95 * .9 * .80))), shifts_per_day=sh, machine_hours_per_line_shift_month=mls, fleet_vehicles=int(round(D0 / (700 * .85))),
              units_per_vehicle_month=700.0, raw_material_stock_units=round(.5 * D0), replenishment_units_month=round(D0 * .992), finished_goods_units=round(.15 * D0), fixed_costs_month=7000000.0)
    return pr, pd.DataFrame([rs])

# ------------------------------ validation and setup ------------------------------
def validate(pr, rs):
    err = []
    for nm, d, cols in (("products", pr, PCOLS), ("resources", rs, RCOLS)):
        m = [c for c in cols if c not in d.columns]
        if m: err.append("%s: missing required column(s): %s (expected: %s)" % (nm, ", ".join(m), ", ".join(cols)))
    if err: raise ValueError(" | ".join(err))
    pr = pr[PCOLS].copy(); rs = rs[RCOLS].copy(); w = []
    for c in PCOLS[1:]: pr[c] = pd.to_numeric(pr[c], errors="coerce")
    for c in RCOLS: rs[c] = pd.to_numeric(rs[c], errors="coerce")
    if len(pr) == 0 or len(rs) == 0: raise ValueError("Both files need at least one data row.")
    b = pr[PCOLS[1:]].isna().any(axis=1)
    if b.any(): err.append("products: rows %s have missing or non-numeric values (nothing is filled in or treated as zero)" % ", ".join(str(i + 2) for i in pr.index[b][:8]))
    n = (pr[PCOLS[1:]] < 0).any(axis=1)
    if n.any(): err.append("products: rows %s contain negative values" % ", ".join(str(i + 2) for i in pr.index[n][:8]))
    d = pr["product"].astype(str).duplicated(keep=False)
    if d.any(): err.append("products: duplicate product names: " + ", ".join(pr["product"][d].astype(str).unique()[:5]))
    r0 = rs.iloc[0]
    if r0.isna().any(): err.append("resources: missing or non-numeric values in: " + ", ".join(r0.index[r0.isna()]))
    if (r0 < 0).any(): err.append("resources: negative values in: " + ", ".join(r0.index[r0 < 0]))
    if not err:
        for c in ("productive_hours_per_employee_month", "units_per_vehicle_month", "machine_hours_per_line_shift_month", "shifts_per_day"):
            if r0[c] <= 0: err.append("resources: %s must be above 0" % c)
        if pr.monthly_units.sum() <= 0: err.append("products: total monthly_units is 0, so there is no baseline demand")
    if err: raise ValueError(" | ".join(err))
    if len(rs) > 1: w.append("resources: %d rows supplied; only the first row is used." % len(rs))
    if (pr.unit_price < pr.unit_variable_cost).any(): w.append("products: some unit_price values are below unit_variable_cost (negative unit margin).")
    return pr, rs.iloc[[0]].reset_index(drop=True), w
def agg(pr):
    u = pr.monthly_units.values.astype(float); D0 = u.sum(); wt = lambda c: float((u * pr[c].values).sum() / D0); return dict(D0=float(D0), price=wt("unit_price"), vc=wt("unit_variable_cost"), lh=wt("labour_h_per_unit"), mh=wt("machine_h_per_unit"))
def setup(pr, rs):
    pr, rs, w = validate(pr, rs); A = agg(pr); r = rs.iloc[0]
    R = dict(emp=float(r.employees), hrs_emp=float(r.productive_hours_per_employee_month), prod_idx=float(r.productivity_index), lines=float(r.machine_lines), shifts=float(r.shifts_per_day), mls=float(r.machine_hours_per_line_shift_month), fleet=float(r.fleet_vehicles), upv=float(r.units_per_vehicle_month), rm=float(r.raw_material_stock_units), repl=float(r.replenishment_units_month), fg=float(r.finished_goods_units), fixed=float(r.fixed_costs_month))
    b = engine(base_P(DEFP), R, A)
    if b["fulfilled"] < b["D"] * .999: w.append("Inconsistent totals: your resources cannot even serve baseline demand (%s of %s units; binding: %s). Check units and monthly vs total figures." % (nf(b["fulfilled"]), nf(b["D"]), b["binding"]))
    return R, A, w, pr, rs
def use_data(pr, rs, demo):
    R, A, w, pr, rs = setup(pr, rs); G.update(R=R, A=A, warn=w, pr=pr, rs=rs, demo=demo)
    if "custom" not in G: G["custom"] = {}

# ------------------------------ parameters ------------------------------
PARAMS = [("Demand & horizon", "g", "Target sales growth (%)", -30, 60, 20, 1), ("Demand & horizon", "horizon", "Simulation horizon (months)", 1, 12, 3, 1), ("Demand & horizon", "price_chg", "Selling-price change (%)", -15, 25, 0, 1),
 ("Workforce", "hires", "Additional hires (FTE)", 0, 100, 0, 1), ("Workforce", "ramp", "Hire ramp-up delay (months)", 0, 6, 0, 1), ("Workforce", "ot", "Overtime (% extra hours, max 25)", 0, 25, 0, 1), ("Workforce", "prod_pct", "Labour productivity (% of standard)", 70, 130, 100, 1),
 ("Inventory & supply", "extra_stock_pct", "Extra opening raw material (% of monthly demand)", 0, 100, 0, 5), ("Inventory & supply", "repl_pct", "Extra replenishment (% above current)", 0, 60, 0, 1), ("Inventory & supply", "disrupt", "Supply disruption (% of replenishment lost)", 0, 80, 0, 5),
 ("Production", "lines_add", "Additional production lines", 0, 20, 0, 1), ("Production", "shifts_add", "Extra shift per day (0 or 1)", 0, 1, 0, 1), ("Production", "util", "Utilisation limit (%)", 60, 100, 90, 1), ("Production", "down", "Downtime (%)", 0, 20, 5, 1),
 ("Logistics", "fleet_add", "Additional vehicles", 0, 40, 0, 1), ("Logistics", "dispatch", "Dispatch efficiency gain (%)", 0, 30, 0, 1), ("Logistics", "deliv", "Delivery cost per unit (₹)", None, None, 40, None),
 ("Costs", "infl", "Variable-cost inflation (%)", 0, 30, 0, 1), ("Costs", "salary", "Salary per employee-month (₹)", None, None, 38000, None), ("Costs", "recruit", "Recruitment cost per hire (₹)", None, None, 40000, None), ("Costs", "ot_prem", "Overtime pay multiple (× hourly wage)", None, None, 1.5, None),
 ("Costs", "line_capex", "Capex per production line (₹)", None, None, 6000000, None), ("Costs", "line_run", "Running cost per line-month (₹)", None, None, 150000, None), ("Costs", "veh_capex", "Capex per vehicle (₹)", None, None, 1800000, None), ("Costs", "veh_run", "Running cost per vehicle-month (₹)", None, None, 60000, None),
 ("Costs", "hold", "Inventory holding cost (% of value per year)", None, None, 18, None), ("Costs", "mat_share", "Material share of variable cost (0-1)", None, None, .6, None),
 ("Uncertainty", "unc", "Uncertainty level (%)", 0, 40, 12, 1), ("Uncertainty", "runs", "Simulation runs (100-5000)", None, None, 800, None), ("Uncertainty", "seed", "Random seed", None, None, 42, None), ("Uncertainty", "svc", "Service-level target (% fulfilled)", 80, 100, 95, 1)]
KEYS = [p[1] for p in PARAMS]; DEFP = {p[1]: float(p[5]) for p in PARAMS}; GROUPS = list(dict.fromkeys(p[0] for p in PARAMS))
EXP = ("hires", "ot", "extra_stock_pct", "repl_pct", "lines_add", "shifts_add", "fleet_add", "dispatch")
def base_P(P): return dict(P, g=0.0, hires=0, ramp=0, ot=0, extra_stock_pct=0, repl_pct=0, lines_add=0, shifts_add=0, fleet_add=0, dispatch=0, disrupt=0, infl=0, price_chg=0, prod_pct=100.0, dmult=1.0, prodmult=1.0, linemult=1.0, fleetmult=1.0, rmult=1.0, pmult=1.0, vmult=1.0, fixmult=1.0)
def getP(vals):
    P = dict(zip(KEYS, vals))
    for k in KEYS:
        if P[k] is None or not np.isfinite(float(P[k])): raise ValueError("Input '%s' is empty or invalid." % k)
        P[k] = float(P[k])
    neg = [k for k in KEYS if k not in ("g", "price_chg") and P[k] < 0]
    if neg: raise ValueError("Negative values are not allowed for: " + ", ".join(neg))
    P["horizon"] = int(max(1, P["horizon"])); P["ramp"] = min(P["ramp"], max(P["horizon"] - 1, 0)); P["ot"] = min(P["ot"], 25.0); P["runs"] = int(min(max(P["runs"], 100), 5000)); return P

# ------------------------------ simulation engine (pure functions) ------------------------------
def dv(a, b): return a / b if b > 0 else (INF if a > 0 else 0.0)
def engine(P, R, A):
    H = P["horizon"]; D = A["D0"] * (1 + P["g"] / 100) * P.get("dmult", 1.0) * H; price = A["price"] * (1 + P["price_chg"] / 100) * P.get("pmult", 1.0); vc = A["vc"] * (1 + P["infl"] / 100) * P.get("vmult", 1.0); fg = R["fg"]
    prod = R["prod_idx"] * P["prod_pct"] / 100 * P.get("prodmult", 1.0); hm = max(0.0, H - P["ramp"]); reg = (R["emp"] * H + P["hires"] * hm) * R["hrs_emp"] * prod; oth = reg * P["ot"] / 100; lab = reg + oth
    mach = (R["lines"] * P.get("linemult", 1.0) + P["lines_add"]) * (R["shifts"] + P["shifts_add"]) * R["mls"] * (1 - P["down"] / 100) * P["util"] / 100 * H
    rm = R["rm"] + P["extra_stock_pct"] / 100 * A["D0"] + R["repl"] * (1 + P["repl_pct"] / 100) * (1 - P["disrupt"] / 100) * P.get("rmult", 1.0) * H
    log = (R["fleet"] * P.get("fleetmult", 1.0) + P["fleet_add"]) * R["upv"] * (1 + P["dispatch"] / 100) * H
    cons = dict(Workforce=fg + dv(lab, A["lh"]), Production=fg + dv(mach, A["mh"]), Inventory=fg + rm, Logistics=log); eps = 1e-9 * max(D, 1.0); lo = min(cons.values()); ful = max(0.0, min(D, lo))
    binding = min(cons, key=cons.get) if lo < D - eps else "None"; material = sorted([k for k, v in cons.items() if v < D - eps], key=cons.get); gaps = {k: max(0.0, D - v) for k, v in cons.items()}
    pu = max(0.0, ful - fg); need = max(0.0, D - fg); lab_used = pu * A["lh"]; req = dict(Workforce=need * A["lh"], Production=need * A["mh"], Inventory=need, Logistics=D); cap = dict(Workforce=lab, Production=mach, Inventory=rm, Logistics=log); load = {k: dv(req[k], cap[k]) for k in RN}
    ot_used = max(0.0, min(oth, lab_used - reg)); wage = P["salary"] / R["hrs_emp"]; rev = ful * price; var = ful * vc; dl = ful * P["deliv"]; fixed = R["fixed"] * P.get("fixmult", 1.0) * H; hire = P["hires"] * (P["salary"] * hm + P["recruit"]); otc = ot_used * wage * P["ot_prem"]
    pexp = P["lines_add"] * P["line_run"] * H + P["shifts_add"] * (R["lines"] + P["lines_add"]) * P["line_run"] * .5 * H; lexp = (P["fleet_add"] + P["dispatch"] / 100 * R["fleet"]) * P["veh_run"] * H
    mv = vc * P["mat_share"]; open_inv = fg * vc + (R["rm"] + P["extra_stock_pct"] / 100 * A["D0"]) * mv; end_inv = max(0.0, fg - ful) * vc + max(0.0, rm - pu) * mv; avg_inv = (open_inv + end_inv) / 2; hold = avg_inv * P["hold"] / 100 / 12 * H
    capex = P["lines_add"] * P["line_capex"] + P["fleet_add"] * P["veh_capex"]; dep = capex / 36 * H; op = rev - var - dl - fixed - hire - otc - pexp - lexp - hold - dep
    return dict(D=D, fulfilled=ful, unmet=D - ful, cons=cons, gaps=gaps, binding=binding, material=material, req=req, cap=cap, load=load, used=dict(Workforce=dv(lab_used, lab), Production=dv(pu * A["mh"], mach), Inventory=dv(pu, rm), Logistics=dv(ful, log)), price=price, vc=vc, rev=rev, var=var, dl=dl, fixed=fixed, hire=hire, otc=otc, pexp=pexp, lexp=lexp, hold=hold, dep=dep, capex=capex, op=op, avg_inv=avg_inv, ot_used=ot_used, reg=reg)
def size(P, R, A):
    Q = dict(P, hires=0, ot=0, extra_stock_pct=0, repl_pct=0, lines_add=0, shifts_add=0, fleet_add=0, dispatch=0, dmult=1.0, ramp=min(1, max(0, int(P["horizon"]) - 1))); H = Q["horizon"]; F = A["D0"] * H * (1 + Q["g"] / 100); need = max(0.0, F - R["fg"]) * 1.02; e = engine(Q, R, A); out = dict(ramp=Q["ramp"], hires=0, lines_add=0, fleet_add=0, repl_pct=0)
    pr_ = R["prod_idx"] * Q["prod_pct"] / 100; hm = H - Q["ramp"]; g1 = need * A["lh"] - e["cap"]["Workforce"]
    if g1 > 1e-9 and hm > 0: out["hires"] = int(math.ceil(g1 / (R["hrs_emp"] * pr_ * hm)))
    g2 = need * A["mh"] - e["cap"]["Production"]; per = R["shifts"] * R["mls"] * (1 - Q["down"] / 100) * Q["util"] / 100 * H
    if g2 > 1e-9 and per > 0: out["lines_add"] = int(math.ceil(g2 / per))
    g3 = F - e["cap"]["Logistics"]
    if g3 > 1e-9 and R["upv"] > 0: out["fleet_add"] = int(math.ceil(g3 / (R["upv"] * H)))
    g4 = need - e["cap"]["Inventory"]; rp = R["repl"] * H * (1 - Q["disrupt"] / 100)
    if g4 > 1e-9 and rp > 0: out["repl_pct"] = int(math.ceil(100 * g4 / rp))
    return out
def presets(P, R, A):
    b = base_P(P); gP = dict(b, g=P["g"], price_chg=P["price_chg"], infl=P["infl"], disrupt=P["disrupt"], prod_pct=P["prod_pct"]); t = dict(gP); t.update(size(t, R, A)); ph = dict(gP, g=round(P["g"] * .6, 2)); ph.update(size(ph, R, A))
    return {"Business as usual": dict(b), "Growth with existing resources": gP, "Growth with targeted expansion": t, "Phased growth (phase 1 = 60% of uplift)": ph}
def verdict(P, e, Dt):
    if e["fulfilled"] < .98 * Dt - 1e-9: return "Not feasible under current assumptions"
    return "Feasible with targeted investment" if any(P[k] > 0 for k in EXP) else "Feasible with current capacity"
def cost_of(x): return x["var"] + x["dl"] + x["fixed"] + x["hire"] + x["otc"] + x["pexp"] + x["lexp"] + x["hold"] + x["dep"]
def krow(P, e, b, A):
    D = e["D"]; H = P["horizon"]; Dt = A["D0"] * (1 + P["g"] / 100) * H; wc = max(0.0, e["avg_inv"] - b["avg_inv"]); fund = e["capex"] + wc; ip = e["op"] - b["op"]
    k = dict(g=P["g"], potential=D, fulfilled=e["fulfilled"], unmet=e["unmet"], service=e["fulfilled"] / D if D > 0 else 1.0, achieve=e["fulfilled"] / Dt if Dt > 0 else 1.0, rev=e["rev"], op=e["op"], margin=e["op"] / e["rev"] if e["rev"] > 0 else np.nan, d_rev=e["rev"] - b["rev"], inc_profit=ip, inc_cost=cost_of(e) - cost_of(b),
             invest=e["capex"], wc=wc, roi=((ip + e["dep"] - b["dep"]) * 12 / H / fund) if fund > 0 else np.nan, binding=e["binding"], verdict=verdict(P, e, Dt))
    for n in RN: k["l_" + n] = e["load"][n]
    return k
def bridge(e, b):
    r = [("Revenue", e["rev"] - b["rev"])] + [(n, -(e[k] - b[k])) for n, k in (("Variable cost", "var"), ("Delivery cost", "dl"), ("Fixed costs", "fixed"), ("Hiring", "hire"), ("Overtime", "otc"), ("Production expansion", "pexp"), ("Logistics expansion", "lexp"), ("Inventory holding", "hold"), ("Depreciation", "dep"))]; return r, sum(v for _, v in r), e["op"] - b["op"]
def breakeven(P, R, A, bop):
    for g in range(0, 61):
        if engine(dict(P, g=float(g)), R, A)["op"] >= bop - 1e-6: return g
    return None
def mc(P, R, A, base, runs, unc, seed):
    rng = np.random.default_rng(int(seed)); u = unc / 100; Dt = A["D0"] * (1 + P["g"] / 100) * P["horizon"]; rows = []
    for _ in range(int(runs)):
        Q = dict(P, dmult=float(np.exp(rng.normal(0, u))), prodmult=float(np.clip(rng.normal(1, u / 2), .7, 1.25)), linemult=float(np.clip(1 - abs(rng.normal(0, u / 3)), .7, 1)), fleetmult=float(np.clip(1 - abs(rng.normal(0, u / 3)), .7, 1)), rmult=float(np.clip(rng.normal(1, u / 2), .5, 1.1)), vmult=float(np.exp(rng.normal(0, u / 4))))
        e = engine(Q, R, A); rows.append(dict(demand=e["D"], fulfilled=e["fulfilled"], service=e["fulfilled"] / e["D"] if e["D"] > 0 else 1.0, op=e["op"], inc=e["op"] - base["op"], achieved=e["fulfilled"] / Dt if Dt > 0 else 1.0, binding=e["binding"]))
    return pd.DataFrame(rows)
def mcsum(d, svc):
    q = lambda s: (s.quantile(.1), s.median(), s.quantile(.9)); return dict(rows=[("Fulfilled units",) + q(d.fulfilled), ("Operating profit",) + q(d.op), ("Incremental profit vs baseline",) + q(d.inc), ("Fulfilment rate",) + q(d.service)], p_target=float((d.achieved >= .98).mean()), p_svc=float((d.service >= svc / 100).mean()), p_pos=float((d.inc > 0).mean()), bind=d.binding.value_counts(normalize=True))
SENS = [("Demand level", "dmult"), ("Labour productivity", "prodmult"), ("Production line capacity", "linemult"), ("Fleet capacity", "fleetmult"), ("Material replenishment", "rmult"), ("Selling price", "pmult"), ("Variable cost", "vmult"), ("Fixed costs", "fixmult")]
def sens(P, R, A):
    rows = []
    for nm, k in SENS:
        o = [engine(dict(P, **{k: f}), R, A) for f in (.9, 1.1)]; rows.append(dict(driver=nm, op_lo=o[0]["op"], op_hi=o[1]["op"], f_lo=o[0]["fulfilled"], f_hi=o[1]["fulfilled"], sv_lo=1 - o[0]["fulfilled"] / o[0]["D"] if o[0]["D"] > 0 else 0, sv_hi=1 - o[1]["fulfilled"] / o[1]["D"] if o[1]["D"] > 0 else 0))
    d = pd.DataFrame(rows); d["swing"] = (d.op_hi - d.op_lo).abs(); return d.sort_values("swing", ascending=False).reset_index(drop=True)

# ------------------------------ strategy advisor (deterministic, evidence-grounded) ------------------------------
def advise(S):
    R, A = G["R"], G["A"]; P, e, k = S["sel"]["P"], S["sel"]["e"], S["sel"]["k"]; H = P["horizon"]; D = e["D"]; out = []; c = sorted(e["cons"].items(), key=lambda t: t[1])
    out.append(("Constraints (evidence)", "Units each resource can support over %d months vs potential demand of %s: " % (H, nf(D)) + "; ".join("%s %s (%s)" % (n, nf(v), sg(v / D - 1) if D > 0 else "n/a") for n, v in c) + ". Binding constraint: **%s**." % e["binding"] + (" Other material bottlenecks: " + ", ".join(m for m in e["material"] if m != e["binding"]) + "." if len(e["material"]) > 1 else "")))
    out.append(("Is %.0f%% growth feasible?" % P["g"], "%s. Fulfilled %s of %s units (%s of target); the %s unmet units (%s of revenue) are one lost-sales pool, attributed once to %s, not added across bottlenecks." % (k["verdict"], nf(e["fulfilled"]), nf(D), pc(k["achieve"]), nf(e["unmet"]), money(e["unmet"] * e["price"]), e["binding"])))
    t = S["out"]["Growth with targeted expansion"]; p_ = S["out"]["Phased growth (phase 1 = 60% of uplift)"]; x = size(dict(P), R, A)
    out.append(("Targeted expansion", "To close every gap for the full target, the model sizes: +%d hires (ramp %d month), +%d production lines, +%d vehicles, +%d%% replenishment. Result: fulfilled %s (%s), operating profit %s (Δ %s vs baseline), capex %s plus working capital %s, annualised return on funding %s." % (x["hires"], x["ramp"], x["lines_add"], x["fleet_add"], x["repl_pct"], nf(t["e"]["fulfilled"]), pc(t["k"]["service"]), money(t["k"]["op"]), money(t["k"]["inc_profit"]), money(t["k"]["invest"]), money(t["k"]["wc"]), pc(t["k"]["roi"]))))
    out.append(("Targeted vs phased", "Phased (%.0f%% growth, sized investment): profit %s (Δ %s), funding %s, fulfilment %s. Targeted (%.0f%%): profit %s (Δ %s), funding %s, fulfilment %s. %s" % (p_["P"]["g"], money(p_["k"]["op"]), money(p_["k"]["inc_profit"]), money(p_["k"]["invest"] + p_["k"]["wc"]), pc(p_["k"]["service"]), t["P"]["g"], money(t["k"]["op"]), money(t["k"]["inc_profit"]), money(t["k"]["invest"] + t["k"]["wc"]), "Targeted earns more profit but needs more funding; phasing limits exposure if demand falls short." if t["k"]["inc_profit"] > p_["k"]["inc_profit"] else "Phasing is at least as profitable under these assumptions.")))
    g1 = e["req"]["Workforce"] - e["cap"]["Workforce"]
    if g1 > 0 and e["reg"] > 0: pct = 100 * g1 / e["reg"]; out.append(("Overtime as a stop-gap", "The workforce gap is %s hours. Overtime of %.1f%% would close it (%s), costing about %s at %.1f× wage; %s." % (nf(g1), pct, "within the 25% cap" if pct <= 25 else "above the 25% cap, so overtime alone is not enough", money(g1 * (G["R"] and 38000 or 0) / R["hrs_emp"] * 1.5 if False else g1 * P["salary"] / R["hrs_emp"] * P["ot_prem"]), P["ot_prem"], "fatigue and quality risks are not modelled")))
    out.append(("Next data to collect", "Replace these assumptions with observed data: hire ramp-up curve (assumed %d month), real downtime (assumed %.0f%%), labour hours per unit by line (constant product mix assumed), supplier lead-time reliability, vehicle trips per month, price elasticity (price/demand assumed independent), and cost per added line or vehicle (user inputs, not observed)." % (P["ramp"], P["down"])))
    return out

# ------------------------------ analysis orchestration ------------------------------
def evalall(P):
    R, A = G["R"], G["A"]; items = list(presets(P, R, A).items()) + [("Current builder scenario", dict(P))] + list(G["custom"].items()); out = {}
    for n, p in items: e = engine(p, R, A); b = engine(base_P(p), R, A); out[n] = dict(P=p, e=e, b=b, k=krow(p, R and e, b, A))
    return out
def analyse(P):
    R, A = G["R"], G["A"]; out = evalall(P); sel = out["Current builder scenario"]; d = mc(P, R, A, sel["b"], P["runs"], P["unc"], P["seed"]); S = dict(P=P, out=out, sel=sel, mc=d, mcs=mcsum(d, P["svc"]), sens=sens(P, R, A), be=breakeven(P, R, A, sel["b"]["op"]), ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")); S["adv"] = advise(S); return S

# ------------------------------ renderers ------------------------------
def r_ctrl(S):
    P, e, b, k = S["sel"]["P"], S["sel"]["e"], S["sel"]["b"], S["sel"]["k"]; kb = krow(base_P(P), b, b, G["A"]); cl = lambda v: C["co"] if v > 1 else (C["am"] if v > .9 else C["fg"])
    h = banner() + "<div class='kg'>" + card("Revenue (fulfilled)", money(e["rev"]), "baseline %s · %s" % (money(b["rev"]), sg((e["rev"] / b["rev"] - 1) if b["rev"] > 0 else np.nan))) + card("Fulfilled vs potential sales", nf(e["fulfilled"]) + " units", "potential %s · fulfilment %s" % (nf(e["D"]), pc(k["service"]))) + card("Operating profit", money(e["op"]), "margin %s · baseline %s (%s)" % (pc(k["margin"], 1), money(b["op"]), pc(kb["margin"], 1))) + \
        card("Incremental operating cost", money(k["inc_cost"]), "vs business as usual") + card("Investment and working capital", money(k["invest"] + k["wc"]), "capex %s + working capital %s" % (money(k["invest"]), money(k["wc"])), C["am"]) + card("Target achievement", pc(k["achieve"]), "of the %.0f%% growth target (feasible if ≥ 98%%)" % P["g"], C["fg"] if k["achieve"] >= .98 else C["co"]) + \
        "".join(card(n + " load", pc(e["load"][n]), "requirement ÷ capacity · used %s" % pc(e["used"][n]), cl(e["load"][n])) for n in RN) + card("Critical bottleneck", e["binding"], "gap %s units" % nf(e["gaps"].get(e["binding"], 0)) if e["binding"] != "None" else "none: demand is met", C["co"] if e["binding"] != "None" else C["fg"]) + "</div>"
    why = ("All four resources support the full demand; the tightest is %s at %s load." % (max(RN, key=lambda n: e["load"][n]), pc(max(e["load"].values())))) if not e["material"] else "Resources that cannot support demand: " + "; ".join("%s supports %s of %s units (short %s)" % (n, nf(e["cons"][n]), nf(e["D"]), nf(e["gaps"][n])) for n in e["material"]) + "."
    h += note("<b>Executive verdict:</b> %s<br>%s Growth is a target, not a forecast: potential demand %s units, feasible output %s, fulfilled sales %s." % (vpill(k["verdict"]), why, nf(e["D"]), nf(min(e["D"], min(e["cons"].values()))), nf(e["fulfilled"])), "ai")
    f1 = go.Figure([go.Bar(x=RN, y=[min(b["load"][n], 3) * 100 for n in RN], name="Baseline", marker_color=C["gg"]), go.Bar(x=RN, y=[min(e["load"][n], 3) * 100 for n in RN], name="Selected scenario", marker_color=C["fg"])]); f1.add_hline(y=100, line_dash="dash", line_color=C["co"]); f1 = sty(f1, 340, "Resource load % (requirement ÷ capacity; above 100 = bottleneck)")
    f2 = go.Figure([go.Bar(x=["Baseline", "Selected scenario"], y=[b["fulfilled"], e["fulfilled"]], name="Fulfilled sales", marker_color=C["fg"]), go.Bar(x=["Baseline", "Selected scenario"], y=[b["unmet"], e["unmet"]], name="Unmet demand", marker_color=C["co"])]); f2.update_layout(barmode="stack"); return h, f1, sty(f2, 340, "Potential demand = fulfilled + unmet (units over the horizon)")
CR = [("Growth target (%)", "g", lambda v: "%.0f%%" % v), ("Potential demand (units)", "potential", nf), ("Fulfilled units", "fulfilled", nf), ("Unmet demand (units)", "unmet", nf), ("Fulfilment rate", "service", pc), ("Target achievement", "achieve", pc), ("Revenue", "rev", money), ("Operating profit", "op", money), ("Operating margin", "margin", lambda v: pc(v, 1)), ("Δ revenue vs baseline", "d_rev", money), ("Δ operating profit vs baseline", "inc_profit", money),
      ("Incremental operating cost", "inc_cost", money), ("Investment (capex)", "invest", money), ("Incremental working capital", "wc", money), ("Annualised return on funding", "roi", pc)] + [(n + " load", "l_" + n, pc) for n in RN] + [("Binding bottleneck", "binding", str), ("Feasibility", "verdict", None)]
def r_comp(S):
    out = S["out"]; names = list(out); rows = []
    for lab, key, fm in CR: rows.append([lab] + [(vpill(out[n]["k"][key]) if fm is None else fm(out[n]["k"][key])) for n in names])
    h = banner() + note("Four preset scenarios are generated from your builder settings (growth target, productivity, price, inflation and disruption); the investments in presets 3 and 4 are <b>auto-sized</b> to close the computed gaps. Phase 1 grows demand by 60% of the target uplift. Deltas are against each scenario's own business-as-usual baseline. Add your own with 'Save current builder scenario'.", "info") + trows(["Metric"] + [esc(n) for n in names], rows)
    f1 = go.Figure([go.Bar(x=RN, y=[min(out[n]["k"]["l_" + r], 3) * 100 for r in RN], name=n) for n in names]); f1.add_hline(y=100, line_dash="dash", line_color=C["co"]); f1 = sty(f1, 360, "Resource load % by scenario (above 100 = bottleneck)")
    f2 = go.Figure([go.Bar(x=names, y=[out[n]["e"][k] for n in names], name=lab) for k, lab in (("hire", "Hiring"), ("otc", "Overtime"), ("pexp", "Production expansion"), ("lexp", "Logistics expansion"), ("hold", "Inventory holding"), ("dep", "Depreciation"))]); f2.update_layout(barmode="stack"); f2.update_xaxes(tickangle=-15); return h, f1, sty(f2, 360, "Expansion-related cost breakdown (₹, excludes variable and fixed base costs)")
def r_cap(S):
    R, A = G["R"], G["A"]; P, e = S["sel"]["P"], S["sel"]["e"]; H = P["horizon"]; unit = dict(Workforce="labour hours", Production="machine hours", Inventory="units", Logistics="units"); prod = R["prod_idx"] * P["prod_pct"] / 100; hmn = max(H - P["ramp"], 0); rows = []
    for n in RN:
        gap = max(0.0, e["req"][n] - e["cap"][n])
        if n == "Workforce": inc = ("≈ %.1f FTE hired (%d productive months)" % (gap / (R["hrs_emp"] * prod * hmn), hmn) if hmn > 0 else "hiring cannot help inside the horizon") + (" or %.1f%% overtime" % (100 * gap / e["reg"]) if e["reg"] > 0 else "")
        elif n == "Production": inc = "≈ %.1f extra lines" % (gap / (R["shifts"] * R["mls"] * (1 - P["down"] / 100) * P["util"] / 100 * H))
        elif n == "Inventory": inc = "≈ %s units of extra supply (%.1f%% of replenishment)" % (nf(gap), 100 * gap / (R["repl"] * H) if R["repl"] > 0 else 0)
        else: inc = "≈ %.1f vehicles" % (gap / (R["upv"] * (1 + P["dispatch"] / 100) * H))
        rows.append([n, unit[n], nf(e["req"][n]), nf(e["cap"][n]), pc(e["load"][n]), nf(e["cons"][n]), nf(e["gaps"][n]), "<b>binding</b>" if n == e["binding"] else ("bottleneck" if n in e["material"] else "ok"), inc if gap > 0 else "none needed"])
    h = banner() + note("Each resource is tested independently over the same %d-month horizon (monthly capacities × months; finished-goods stock %s units counts toward output). <b>Max units supported</b> = stock + what that resource can add. Fulfilled sales = the lowest of these and demand, so a bigger line cannot create sales if inventory or delivery is short. The unmet quantity is counted once and attributed to the binding resource; other gaps are shown as secondary, not added." % (H, nf(R["fg"])), "info")
    h += trows(["Resource", "Unit", "Required", "Capacity", "Load", "Max units supported", "Gap (units)", "Status", "Incremental resource to close gap"], rows)
    x = size(dict(P), R, A); h += note("<b>Auto-sized plan to meet the full target</b> (3% buffer, ramp %d month): +%d hires, +%d lines, +%d vehicles, +%d%% replenishment." % (x["ramp"], x["hires"], x["lines_add"], x["fleet_add"], x["repl_pct"]), "ai")
    f = go.Figure([go.Bar(x=RN, y=[min(e["cons"][n], e["D"] * 3) for n in RN], marker_color=[C["co"] if n in e["material"] else C["fg"] for n in RN], name="Max units supported")]); f.add_hline(y=e["D"], line_dash="dash", line_color=C["am"], annotation_text="Potential demand"); return h, sty(f, 360, "Maximum units each resource can support vs potential demand (coral = bottleneck)")
def r_fin(S):
    e, b, k, P = S["sel"]["e"], S["sel"]["b"], S["sel"]["k"], S["sel"]["P"]; L = [("Revenue", "rev"), ("Variable cost", "var"), ("Delivery cost", "dl"), ("Fixed operating cost", "fixed"), ("Hiring (salaries + recruitment)", "hire"), ("Overtime cost", "otc"), ("Production expansion running cost", "pexp"), ("Logistics expansion running cost", "lexp"), ("Inventory holding cost", "hold"), ("Depreciation of capex (36 months)", "dep"), ("Operating profit", "op")]
    br, tot, act = bridge(e, b); be = S["be"]; ctr = e["rev"] - e["var"] - e["dl"]
    h = banner() + note("Revenue comes only from <b>fulfilled</b> sales, so lost sales appear once (as lower revenue) and are never subtracted again. Operating profit = revenue − variable − delivery − fixed − expansion costs − holding − depreciation. Contribution margin = revenue − variable − delivery = %s (%s of revenue)." % (money(ctr), pc(ctr / e["rev"], 1) if e["rev"] > 0 else "—"), "info")
    h += trows(["Line (horizon total)", "Baseline", "Selected scenario", "Δ"], [[a, money(b[c]), money(e[c]), money(e[c] - b[c])] for a, c in L])
    h += "<div class='kg'>" + card("Incremental profit", money(k["inc_profit"]), "vs business as usual") + card("Break-even sales uplift", ("%d%%" % be) if be is not None else "not reached (0-60%)", "smallest growth at which this resource plan matches baseline profit") + card("Funding required", money(k["invest"] + k["wc"]), "capex + incremental working capital", C["am"]) + card("Annualised return on funding", pc(k["roi"]), "(Δprofit + Δdepreciation) × 12/%d ÷ funding; only if funding > 0" % P["horizon"]) + "</div>"
    h += SEC("Profit bridge (reconciles exactly)") + trows(["Component", "Impact on operating profit"], [[a, money(v)] for a, v in br] + [["<b>Total of bridge</b>", "<b>%s</b>" % money(tot)], ["Actual Δ operating profit", money(act)]]) + note("Opportunity note (not in the bridge, to avoid double counting): unmet demand of %s units is worth %s of revenue at the scenario price." % (nf(e["unmet"]), money(e["unmet"] * e["price"])), "info")
    f = go.Figure(go.Waterfall(x=[a for a, _ in br] + ["Δ operating profit"], measure=["relative"] * len(br) + ["total"], y=[v / 1e6 for _, v in br] + [0], increasing=dict(marker=dict(color=C["sg"])), decreasing=dict(marker=dict(color=C["co"])), totals=dict(marker=dict(color=C["fg"])))); f.update_xaxes(tickangle=-30); return h, sty(f, 380, "Profit bridge vs baseline (₹ million)")
def r_unc(S):
    P, e, m = S["sel"]["P"], S["sel"]["e"], S["mcs"]; d = S["mc"]; fm = [nf, money, money, lambda v: pc(v, 1)]
    h = banner() + note("<b>Model-based estimates conditional on your assumptions, not guaranteed probabilities and not statistically validated confidence intervals.</b> %d runs (seed %d): demand ~ lognormal(σ=%.0f%%), labour productivity, line downtime, fleet availability, supply reliability and variable cost vary around the selected scenario. The baseline is held at its deterministic value." % (P["runs"], P["seed"], P["unc"]), "warn")
    h += trows(["Outcome", "P10", "Median", "P90"], [[r[0]] + [fm[i](v) for v in r[1:]] for i, r in enumerate(m["rows"])]) + "<div class='kg'>" + card("Chance of reaching the target", pc(m["p_target"]), "fulfilled ≥ 98% of the %.0f%% growth target (model-based)" % P["g"]) + card("Chance of meeting service level", pc(m["p_svc"]), "fulfilment ≥ %.0f%% of each run's demand" % P["svc"]) + card("Chance of positive incremental profit", pc(m["p_pos"]), "vs deterministic baseline") + "</div>"
    h += note("Most frequent binding constraint across runs: " + ", ".join("%s %s" % (k, pc(v)) for k, v in m["bind"].head(4).items()) + ".", "info"); s = S["sens"]
    h += SEC("Sensitivity: ±10% on each assumption, one at a time") + trows(["Driver", "Profit at −10%", "Profit at +10%", "Fulfilled at −10%", "Fulfilled at +10%", "Shortfall at −10%", "Shortfall at +10%"], [[r.driver, money(r.op_lo), money(r.op_hi), nf(r.f_lo), nf(r.f_hi), pc(r.sv_lo, 1), pc(r.sv_hi, 1)] for r in s.itertuples()])
    f1 = go.Figure(go.Histogram(x=d.inc / 1e6, nbinsx=30, marker_color=C["fg"])); f1.add_vline(x=0, line_dash="dash", line_color=C["co"]); f1 = sty(f1, 330, "Distribution of incremental operating profit across runs (₹ million)")
    f2 = go.Figure([go.Bar(y=s.driver, x=(s.op_lo - e["op"]) / 1e6, orientation="h", name="−10%", marker_color=C["co"]), go.Bar(y=s.driver, x=(s.op_hi - e["op"]) / 1e6, orientation="h", name="+10%", marker_color=C["sg"])]); f2.update_layout(barmode="overlay"); f2.update_yaxes(autorange="reversed"); return h, f1, sty(f2, 330, "Tornado: change in operating profit (₹ million)")
def r_adv(S): return "### Strategy advisor (deterministic, computed from the simulation)\n" + "\n".join("- **%s**: %s" % (a, b) for a, b in S["adv"]) + "\n\n*Recommendations quote the simulated figures above; they are decision support, not guarantees. Management judgement is required.*"
def r_data():
    h = banner() + "".join(note(esc(w), "warn") for w in G["warn"]) + SEC("Products (monthly baseline)") + trows(PCOLS, [[esc(v) if isinstance(v, str) else format(v, ",.2f") for v in r] for r in G["pr"].values.tolist()]) + SEC("Resources (one row)") + trows(RCOLS, [[format(v, ",.2f") for v in G["rs"].iloc[0].values]])
    A = G["A"]; return h + note("Aggregates used (constant product mix assumed): %s units/month, average price %s, variable cost %s, %.3f labour h/unit, %.3f machine h/unit." % (nf(A["D0"]), money(A["price"]), money(A["vc"]), A["lh"], A["mh"]), "info") + note("Tests: " + " · ".join("%s %s" % ("PASS" if ok else "FAIL", n) for g, n, ok, d in TESTS), "ok" if all(t[2] for t in TESTS) else "err")
def run_all(*vals):
    try:
        P = getP(vals); S = analyse(P); G["last"] = S; a, b, c = r_ctrl(S); d, e, f = r_comp(S); g, h = r_cap(S); i, j = r_fin(S); k, l, m = r_unc(S)
        return (note("Simulation refreshed for %d scenarios (%s)." % (len(S["out"]), S["ts"]), "ok"), a, b, c, d, e, f, g, h, i, j, k, l, m, r_adv(S), r_data())
    except Exception as ex: return (note("Could not run the simulation: " + esc(ex), "err"),) + (None,) * 15
def save_sc(name, *vals):
    try:
        P = getP(vals); n = "Custom: " + (name or "Scenario %d" % (len(G["custom"]) + 1)).strip(); G["custom"][n] = P; return note("Saved '%s' for this session; it appears in the comparison." % esc(n), "ok")
    except Exception as ex: return note("Not saved: " + esc(ex), "err")
def load_data(pf, rf):
    try:
        if pf is None and rf is None: pr, rs = make_data(); use_data(pr, rs, True); return note("Using the synthetic demo data.", "ok")
        if pf is None or rf is None: raise ValueError("Upload both products.csv and resources.csv, or neither.")
        rd = lambda f: pd.read_csv(f if isinstance(f, str) else f.name); use_data(rd(pf), rd(rf), False); return note("Uploaded data validated and loaded.", "ok") + "".join(note(esc(w), "warn") for w in G["warn"])
    except Exception as ex: return note("Upload rejected (previous data kept): " + esc(ex), "err")

# ------------------------------ exports ------------------------------
def export_all():
    if "last" not in G: return None, note("Run the simulation first.", "info")
    S = G["last"]; out = []; ts = S["ts"]; sel = S["sel"]; e = sel["e"]; cdef = "Definitions: fulfilled = min(demand, max units each resource supports); load = requirement ÷ capacity; incremental = vs the scenario's business-as-usual baseline; ROI annualised on capex + incremental working capital."
    def w(df, fn): df.to_csv(fn, index=False); out.append(fn)
    w(pd.DataFrame([dict(scenario=n, **{kk: v for kk, v in d["k"].items()}) for n, d in S["out"].items()]).assign(generated=ts, data_type="simulated outputs from " + ("synthetic" if G.get("demo") else "uploaded") + " inputs"), "simul8_scenario_comparison.csv")
    w(pd.DataFrame([dict(resource=n, required=e["req"][n], capacity=e["cap"][n], load=e["load"][n], max_units_supported=e["cons"][n], gap_units=e["gaps"][n], binding=(n == e["binding"])) for n in RN]).assign(scenario="Current builder scenario", generated=ts), "simul8_kpi_bottleneck_report.csv")
    w(pd.DataFrame([dict(outcome=r[0], p10=r[1], median=r[2], p90=r[3]) for r in S["mcs"]["rows"]] + [dict(outcome="P(target reached)", median=S["mcs"]["p_target"]), dict(outcome="P(service level met)", median=S["mcs"]["p_svc"]), dict(outcome="P(positive incremental profit)", median=S["mcs"]["p_pos"])]).assign(runs=S["P"]["runs"], seed=S["P"]["seed"], note="model-based, conditional on assumptions"), "simul8_simulation_summary.csv")
    w(S["mc"], "simul8_simulation_runs.csv"); w(pd.DataFrame([dict(setting=k, value=v) for k, v in S["P"].items()]), "simul8_settings.csv")
    lim = "# SIMUL8 AI: assumptions and limitations\nGenerated %s. %s\n\n- Simulated outputs, not observed performance. Input data: %s.\n- Constant product mix; labour, machine and delivery capacity are monthly totals × horizon.\n- Price, demand and productivity are independent unless stated; no price elasticity.\n- Hiring is productive only after the ramp delay; overtime capped at 25%%.\n- Uncertainty ranges are conditional on assumptions and are not validated confidence intervals.\n- Costs of new lines, vehicles and hires are user inputs.\n- No OR-Tools optimisation; auto-sizing is a deterministic heuristic.\n" % (ts, cdef, "SYNTHETIC demo data" if G.get("demo") else "user-uploaded")
    open("simul8_assumptions_limitations.md", "w", encoding="utf-8").write(lim); out.append("simul8_assumptions_limitations.md"); k = sel["k"]; css = "body{font-family:Inter,Arial,sans-serif;background:#F5F2E9;color:#263B37;max-width:900px;margin:30px auto;padding:0 18px}h1{color:#193B37}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px 10px}"
    body = "<h1>SIMUL8 AI: Executive summary</h1><p><i>Generated %s. %s</i></p><p>%s</p><h2>Verdict: %s</h2><p>Fulfilled %s of %s units; operating profit %s (Δ %s vs baseline); binding constraint: %s.</p><h2>Scenario settings</h2><table>%s</table><h2>Scenario comparison</h2><table><tr><th>Scenario</th><th>Feasibility</th><th>Fulfilment</th><th>Operating profit</th><th>Funding</th></tr>%s</table><h2>Advisor</h2><ul>%s</ul><p>%s</p>" % (
        ts, esc(cdef), "Data: SYNTHETIC (fictional) inputs; all results are simulated." if G.get("demo") else "Data: uploaded inputs; all results are simulated.", esc(k["verdict"]), nf(e["fulfilled"]), nf(e["D"]), money(k["op"]), money(k["inc_profit"]), esc(e["binding"]), "".join("<tr><td>%s</td><td>%s</td></tr>" % (esc(a), esc(b)) for a, b in S["P"].items()),
        "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (esc(n), esc(d["k"]["verdict"]), pc(d["k"]["service"]), money(d["k"]["op"]), money(d["k"]["invest"] + d["k"]["wc"])) for n, d in S["out"].items()), "".join("<li><b>%s</b>: %s</li>" % (esc(a), esc(b).replace("**", "")) for a, b in S["adv"]), "Decision support only: simulated, not guaranteed.")
    open("simul8_executive_summary.html", "w", encoding="utf-8").write("<html><head><meta charset='utf-8'><title>SIMUL8 AI</title><style>" + css + "</style></head><body>" + body + "</body></html>"); out.append("simul8_executive_summary.html"); return [f for f in out if os.path.exists(f)], note("Wrote %d report files." % len(out), "ok")

# ------------------------------ self-tests ------------------------------
def run_selftests(verbose=True):
    if TESTS: return TESTS
    T = []; R, A = G["R"], G["A"]; pr0, rs0 = make_data(); D0 = DEFP; H = 3
    def chk(g, n, fn):
        try: ok, d = fn(); T.append((g, n, bool(ok), d))
        except Exception as ex: T.append((g, n, False, type(ex).__name__ + ": " + str(ex)[:90]))
    def msg(f):
        try: f(); return ""
        except ValueError as ex: return str(ex)
    def t1(): a = msg(lambda: validate(pr0.drop(columns=["unit_price"]), rs0)); b = pr0.copy(); b.loc[0, "monthly_units"] = -5; c = msg(lambda: validate(b, rs0)); d = pr0.copy(); d.loc[1, "unit_price"] = "abc"; d2 = msg(lambda: validate(d, rs0)); u = msg(lambda: validate(pd.concat([pr0, pr0.iloc[[0]]]), rs0)); return "unit_price" in a and "negative" in c and "non-numeric" in d2 and "duplicate" in u, "missing column, negative value, non-numeric cell and duplicate product are rejected with row references"
    def t2(): e = engine(base_P(D0), R, A); return abs(e["fulfilled"] - A["D0"] * H) < 1e-6 and e["binding"] == "None" and max(e["load"].values()) < 1, "baseline serves its full demand of %s units; tightest load %s" % (nf(e["D"]), pc(max(e["load"].values())))
    def t3(): e = engine(dict(D0, g=20.0), R, A); return abs(e["D"] - A["D0"] * 1.2 * H) < 1e-6, "20%% growth gives demand %s = 1.2 × baseline" % nf(e["D"])
    def t4(): e = engine(dict(D0, g=20.0), R, A); x = R["fg"] + R["emp"] * H * R["hrs_emp"] * R["prod_idx"] / A["lh"]; return e["binding"] == "Workforce" and abs(e["fulfilled"] - x) < 1e-6, "workforce binds: fulfilled %s = stock + hours ÷ hours per unit (hand calculation %s)" % (nf(e["fulfilled"]), nf(x))
    def t5(): e = engine(base_P(D0), dict(R, rm=0.0, repl=0.0), A); return e["binding"] == "Inventory" and abs(e["fulfilled"] - R["fg"]) < 1e-6, "no raw material: fulfilled = finished-goods stock %s, binding Inventory" % nf(R["fg"])
    def t6(): e = engine(base_P(D0), dict(R, lines=1.0), A); x = R["fg"] + 1 * R["shifts"] * R["mls"] * .95 * .9 * H / A["mh"]; return e["binding"] == "Production" and abs(e["fulfilled"] - x) < 1e-6, "one line: production binds at %s units (hand calculation %s)" % (nf(e["fulfilled"]), nf(x))
    def t7(): e = engine(base_P(D0), dict(R, fleet=1.0), A); return e["binding"] == "Logistics" and abs(e["fulfilled"] - R["upv"] * H) < 1e-6, "one vehicle: logistics binds at %s units" % nf(e["fulfilled"])
    def t8(): e = engine(dict(D0, g=20.0), R, A); return len(e["material"]) >= 2 and "Workforce" in e["material"] and "Logistics" in e["material"] and abs(e["unmet"] - (e["D"] - e["fulfilled"])) < 1e-6, "material bottlenecks %s; unmet units counted once (%s)" % (e["material"], nf(e["unmet"]))
    def t9(): z = engine(base_P(D0), R, dict(A, D0=0.0)); c = engine(base_P(D0), dict(R, emp=0.0), A); s = engine(base_P(D0), dict(R, fg=0.0, rm=0.0, repl=0.0), A); return z["fulfilled"] == 0 and z["op"] == -R["fixed"] * H + (z["op"] + R["fixed"] * H) and abs(c["fulfilled"] - R["fg"]) < 1e-6 and s["fulfilled"] == 0, "zero demand, zero workforce (fulfils only stock) and no stock at all run without errors"
    def t10(): P = dict(D0, g=20.0); e = engine(P, R, A); b = engine(base_P(P), R, A); r, tot, act = bridge(e, b); chk_ = e["rev"] - e["var"] - e["dl"] - e["fixed"] - e["hire"] - e["otc"] - e["pexp"] - e["lexp"] - e["hold"] - e["dep"]; return abs(tot - act) < 1e-6 and abs(chk_ - e["op"]) < 1e-6, "profit bridge sums to the actual change %s; profit identity holds" % money(act)
    def t11(): P = dict(D0, g=20.0); a = mc(P, R, A, engine(base_P(P), R, A), 200, 15, 1); b = mc(P, R, A, engine(base_P(P), R, A), 200, 15, 1); c = mc(P, R, A, engine(base_P(P), R, A), 200, 15, 2); return a.equals(b) and not a.equals(c), "same seed gives identical runs; a different seed differs"
    def t12(): o = evalall(dict(D0, g=20.0)); n = list(o); ex, tg = o["Growth with existing resources"], o["Growth with targeted expansion"]; return tg["e"]["fulfilled"] >= ex["e"]["fulfilled"] and tg["k"]["achieve"] >= .98 and ex["k"]["verdict"] == "Not feasible under current assumptions" and tg["k"]["verdict"] == "Feasible with targeted investment" and o["Business as usual"]["k"]["verdict"] == "Feasible with current capacity", "existing resources: %s; targeted expansion reaches %s of target with %s" % (pc(ex["k"]["achieve"]), pc(tg["k"]["achieve"]), {k: v for k, v in tg["P"].items() if k in ("hires", "lines_add", "fleet_add", "repl_pct")})
    def t13(): P = dict(D0, g=20.0); s = sens(P, R, A); e = engine(P, R, A); lo = engine(dict(P, dmult=.9), R, A); return len(s) == len(SENS) and s.swing.is_monotonic_decreasing and lo["D"] < e["D"], "sensitivity table ranks %d drivers by profit swing (top: %s)" % (len(s), s.driver.iloc[0])
    def t14(): out = run_all(*[D0[k] for k in KEYS]); S = G["last"]; return nf(S["sel"]["e"]["fulfilled"]) in out[1] and money(S["sel"]["e"]["op"]) in out[1], "Control Room shows the engine's fulfilled units %s and profit %s" % (nf(S["sel"]["e"]["fulfilled"]), money(S["sel"]["e"]["op"]))
    def t15(): run_all(*[D0[k] for k in KEYS]); f, _ = export_all(); n = len(pd.read_csv("simul8_scenario_comparison.csv")); return n == len(G["last"]["out"]) and "simul8_executive_summary.html" in f, "%d files written; comparison export has %d rows matching the scenarios" % (len(f), n)
    for g, n, f in [("validation", "invalid uploads rejected", t1), ("baseline", "baseline serves baseline demand", t2), ("baseline", "demand growth", t3), ("constraints", "workforce capacity", t4), ("constraints", "inventory constraint", t5), ("constraints", "production constraint", t6), ("constraints", "logistics constraint", t7), ("constraints", "multiple bottlenecks", t8), ("constraints", "zero demand, zero capacity, no stock", t9),
                    ("financial", "profit identity and bridge", t10), ("uncertainty", "reproducible simulation", t11), ("scenario", "scenario comparison and verdicts", t12), ("uncertainty", "sensitivity", t13), ("ui", "UI output matches engine", t14), ("reporting", "CSV export consistency", t15)]: chk(g, n, f)
    TESTS[:] = T
    if verbose:
        for g, n, ok, d in T: print(("PASS " if ok else "FAIL ") + g + ": " + n + " :: " + d)
        print("Result: %d of %d self-tests passed." % (sum(1 for t in T if t[2]), len(T)))
    return TESTS

# ------------------------------ project export ------------------------------
ALGO = """## How SIMUL8 AI works: the 10-step algorithm
1. **Load and validate.** Read products and resources (or the synthetic demo), reject missing, negative, duplicate or non-numeric values with row references, and warn when the resources cannot serve baseline demand.
2. **Aggregate the baseline.** Convert product data into monthly demand, mix-weighted price, variable cost, labour and machine hours per unit, assuming a constant product mix.
3. **Set the target.** Potential demand = baseline units × (1 + growth) × horizon. Growth is a target, not a guaranteed outcome.
4. **Convert to workload.** Units still to produce (demand minus finished-goods stock) become labour hours, machine hours, material units and shipments over the same horizon.
5. **Compute each capacity.** Workforce (hires after ramp, productivity, overtime), production (lines, shifts, downtime, utilisation limit), inventory (stock plus replenishment, disruption) and logistics (fleet, dispatch efficiency).
6. **Find feasible sales.** Fulfilled = minimum of demand and the units each resource can support; the binding constraint is the lowest, and unmet demand is attributed once.
7. **Cost and profit.** Revenue from fulfilled sales only, variable, delivery, fixed, hiring, overtime, expansion, holding and depreciation costs; a profit bridge reconciles exactly to the change versus baseline.
8. **Size and compare strategies.** Auto-size hires, lines, vehicles and replenishment to close gaps, then compare business as usual, growth with existing resources, targeted expansion and phased growth.
9. **Stress-test.** Seeded Monte Carlo (demand, productivity, downtime, fleet, supply, cost) gives P10/median/P90 and model-based chances; ±10% sensitivity ranks the drivers.
10. **Advise and report.** A deterministic advisor quotes the computed figures, and CSV and HTML reports record settings, definitions, timestamp and simulated-versus-observed labels for human review.
"""
METH = ALGO + "\n### Notes\n- All outputs are simulated estimates. Probabilities are model-based and conditional on assumptions.\n- Not included: Streamlit (Gradio is used), OR-Tools, PDF export, product-level capacity, price elasticity.\n"
LICENSE = "MIT License\n\nCopyright (c) 2026 SIMUL8 AI contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"
README = """# SIMUL8 AI: What-If Business Simulator
Test the decision. Before you make it.

Tests whether a 20% sales increase can be supported by existing employees, inventory, production capacity and logistics, which resource binds first, what investment is needed, and how profit, investment and service level trade off. Bundled data is **fictional synthetic data**: a home-appliance maker whose workforce (about 90% loaded) and delivery fleet (about 86% loaded) become binding at +20%, while inventory is tight and production has slack.

""" + ALGO + """
## Architecture
@@@mermaid
flowchart LR
  A[CSV or synthetic data] --> B[Validation]
  B --> C[Baseline aggregates]
  C --> D[Resource-constrained engine]
  D --> E[Scenarios + auto-sizing]
  D --> F[Monte Carlo + sensitivity]
  E --> G[Advisor + reports]
  F --> G
@@@

## Run
@@@
pip install -r requirements.txt
python app.py
@@@
In Google Colab paste `app.py` into one cell and run it; Gradio prints a public link.

## Sample schema
`products.csv`: product, monthly_units, unit_price, unit_variable_cost, labour_h_per_unit, machine_h_per_unit. `resources.csv` (one row): employees, productive_hours_per_employee_month, productivity_index, machine_lines, shifts_per_day, machine_hours_per_line_shift_month, fleet_vehicles, units_per_vehicle_month, raw_material_stock_units, replenishment_units_month, finished_goods_units, fixed_costs_month. Currency is ₹; capacities are monthly.

## Formulas
Demand = baseline × (1+g) × horizon. Fulfilled = min(demand, stock + labour hours ÷ h/unit, stock + machine hours ÷ h/unit, stock + material supply, delivery capacity). Operating profit = revenue − variable − delivery − fixed − hiring − overtime − expansion − holding − depreciation.

## Testing and limits
`pip install pytest && pytest tests` runs the built-in self-tests. Estimates are not guarantees; this is decision support only. Add screenshots to `screenshots/` (none included).
""".replace("@@@", "`" * 3)
TFILE = "from app import run_selftests\n\n\ndef test_%s():\n    res = [r for r in run_selftests(verbose=False) if r[0] in %s]\n    assert res and all(r[2] for r in res), res\n"
def _src():
    try: return open(__file__, encoding="utf-8").read()
    except Exception: pass
    try:
        for s in list(get_ipython().user_ns.get("In") or [])[::-1]:
            if "SIMUL8 AI — What-If Business Simulator" in s and "def main" in s: return s
    except Exception: pass
    return None
def build_project():
    root = "simul8-ai-business-simulator"; pr, rs = make_data()
    for d in ["data/sample", "tests", "docs", "screenshots"]: os.makedirs(os.path.join(root, d), exist_ok=True)
    pr.to_csv(root + "/data/sample/products.csv", index=False); rs.to_csv(root + "/data/sample/resources.csv", index=False); src = _src()
    if src: open(root + "/app.py", "w", encoding="utf-8").write(src)
    W = {"requirements.txt": "gradio>=4.44,<6\nplotly\npandas\nnumpy\n", "README.md": README, "LICENSE": LICENSE, ".gitignore": "__pycache__/\n.ipynb_checkpoints/\n*.zip\nsimul8_*.csv\nsimul8_*.md\nsimul8_*.html\n.env\n", "docs/methodology.md": METH, "docs/data_dictionary.md": "# Data dictionary\nSee README. All sample data is synthetic and fictional.\n", "docs/assumptions_and_limitations.md": "# Assumptions and limitations\nConstant product mix; no price elasticity; hires productive after ramp; user-supplied expansion costs; model-based uncertainty only; no OR-Tools.\n", "screenshots/README.md": "# Screenshots\nAdd your own screenshots here.\n"}
    for nm, g in [("simulation", "('baseline','constraints')"), ("scenario_engine", "('scenario',)"), ("data_validation", "('validation',)"), ("financials", "('financial',)"), ("uncertainty", "('uncertainty',)"), ("ui_reporting", "('ui','reporting')")]: W["tests/test_%s.py" % nm] = TFILE % (nm, g)
    for fn, tx in W.items(): open(os.path.join(root, fn), "w", encoding="utf-8").write(tx)
    z = "simul8_ai_project.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fs in os.walk(root):
            for f in fs: zf.write(os.path.join(dp, f))
    return z, bool(src)

# ------------------------------ UI ------------------------------
CSS = """
.gradio-container{background:#F5F2E9!important;color:#263B37!important;font-family:Inter,system-ui,-apple-system,sans-serif!important;max-width:1400px!important}
.hdr{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;padding:24px 30px;border-radius:14px;background:#193B37;color:#F5F2E9;margin-bottom:12px}.brand{display:flex;gap:16px;align-items:center}
.logo{width:52px;height:52px;border-radius:12px;background:#BCE8B0;color:#193B37;font-weight:800;font-size:20px;display:flex;align-items:center;justify-content:center}.hdr h1{margin:0;font-size:28px;letter-spacing:2px;color:#F5F2E9}.hdr h1 span{color:#E8B96A}.hdr p{margin:4px 0 0;color:#D6C8F0;font-style:italic}
.badges span{display:inline-block;margin:3px;padding:4px 11px;border-radius:6px;background:#ffffff1a;color:#F5F2E9;font-size:12px}button[role=tab]{background:#193B37!important;color:#F5F2E9!important;border-radius:8px 8px 0 0!important;margin-right:2px}button[role=tab][aria-selected=true]{background:#E8B96A!important;color:#193B37!important;font-weight:700}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:10px 0}.kc{background:#fff;border:1px solid #193B3726;border-radius:10px;padding:14px 16px}.kl{color:#5d726c;font-size:11px;text-transform:uppercase;letter-spacing:1.1px}.kv{font-size:22px;font-weight:700;margin:6px 0 4px}.kd{color:#5d726c;font-size:12px}
.note{background:#fff;padding:10px 14px;border-radius:8px;margin:8px 0;color:#263B37;font-size:14px;line-height:1.5;border:1px solid #193B3718}.sec{font-size:15px;font-weight:700;color:#193B37;margin:18px 0 6px;text-transform:uppercase;letter-spacing:1px}
.pill{display:inline-block;border-radius:99px;padding:2px 10px;font-size:11px;font-weight:700;color:#193B37;white-space:nowrap}.tw{overflow-x:auto;border-radius:8px;border:1px solid #193B3726;margin:8px 0;background:#fff}table{border-collapse:collapse;width:100%;font-size:13px}
th{background:#193B37;color:#F5F2E9;text-align:left;padding:9px 10px;font-weight:600}td{padding:8px 10px;border-top:1px solid #193B3712;color:#263B37;vertical-align:top}tr:hover td{background:#BCE8B022}button.primary{background:#193B37!important;color:#F5F2E9!important;border:none!important;font-weight:700!important}@media(max-width:640px){.hdr h1{font-size:21px}.kv{font-size:19px}}
"""
HEADER = "<div class='hdr'><div class='brand'><div class='logo'>S8</div><div><h1>SIMUL8 <span>AI</span></h1><p>Test the decision. Before you make it.</p></div></div><div class='badges'><span>Simulated, not observed</span><span>Growth is a target</span><span>Human review required</span><span>No API key needed</span></div></div>"
def build_ui(zip_path, sfiles):
    with gr.Blocks(css=CSS, title="SIMUL8 AI", theme=gr.themes.Base(primary_hue="green", neutral_hue="stone")) as demo:
        gr.HTML(HEADER); status = gr.HTML(note("Loading the synthetic business and running the simulation...", "info")); comps = {}
        with gr.Tabs():
            with gr.Tab("Executive Control Room"):
                cr_h = gr.HTML()
                with gr.Row():
                    cr1 = gr.Plot(); cr2 = gr.Plot()
            with gr.Tab("Scenario Builder"):
                gr.Markdown("Set assumptions, then press **Run simulation**. Every input changes the results. Costs are illustrative ₹ assumptions, not observed.")
                for grp in GROUPS:
                    items = [p for p in PARAMS if p[0] == grp]
                    with gr.Accordion(grp, open=(grp in ("Demand & horizon", "Workforce"))):
                        for i in range(0, len(items), 3):
                            with gr.Row():
                                for p in items[i:i + 3]: comps[p[1]] = gr.Number(value=p[5], label=p[2]) if p[3] is None else gr.Slider(p[3], p[4], value=p[5], step=p[6], label=p[2])
                with gr.Row():
                    run_b = gr.Button("Run simulation", variant="primary"); rs_b = gr.Button("Reset to defaults"); sv_n = gr.Textbox(label="Name for saved scenario"); sv_b = gr.Button("Save current builder scenario")
                sv_h = gr.HTML()
            with gr.Tab("Scenario Comparison"):
                cp_h = gr.HTML()
                with gr.Row():
                    cp1 = gr.Plot(); cp2 = gr.Plot()
            with gr.Tab("Capacity & Bottlenecks"):
                ca_h = gr.HTML(); ca1 = gr.Plot()
            with gr.Tab("Financial Impact"):
                fi_h = gr.HTML(); fi1 = gr.Plot()
            with gr.Tab("Uncertainty & Sensitivity"):
                un_h = gr.HTML()
                with gr.Row():
                    un1 = gr.Plot(); un2 = gr.Plot()
            with gr.Tab("Strategy Advisor"):
                ad_m = gr.Markdown()
            with gr.Tab("Data Explorer & Uploads"):
                gr.Markdown("Upload **products.csv** and **resources.csv** together (templates below), or leave empty for the synthetic demo. Missing or invalid values are rejected, never treated as zero.")
                with gr.Row():
                    pf = gr.File(label="products.csv", file_types=[".csv"]); rf = gr.File(label="resources.csv", file_types=[".csv"])
                ld_b = gr.Button("Validate and load", variant="primary"); ld_h = gr.HTML(); gr.File(value=sfiles, label="Sample CSV templates (synthetic)", file_count="multiple", interactive=False); da_h = gr.HTML()
            with gr.Tab("Reports & Exports"):
                xp_b = gr.Button("Generate reports", variant="primary"); xp_m = gr.HTML(); xp_f = gr.File(label="Reports", file_count="multiple", interactive=False); gr.File(value=zip_path, label="Download GitHub-ready project (ZIP)", interactive=False)
            with gr.Tab("Methodology"):
                gr.Markdown(METH)
        IN = [comps[k] for k in KEYS]; OUT = [status, cr_h, cr1, cr2, cp_h, cp1, cp2, ca_h, ca1, fi_h, fi1, un_h, un1, un2, ad_m, da_h]
        run_b.click(run_all, IN, OUT, show_progress="full"); demo.load(run_all, IN, OUT); rs_b.click(lambda: [DEFP[k] for k in KEYS], None, IN).then(run_all, IN, OUT); sv_b.click(save_sc, [sv_n] + IN, sv_h).then(run_all, IN, OUT); ld_b.click(load_data, [pf, rf], ld_h).then(run_all, IN, OUT); xp_b.click(export_all, None, [xp_f, xp_m], show_progress="full")
    return demo
def main():
    pr, rs = make_data(); use_data(pr, rs, True); os.makedirs("sample_data", exist_ok=True); pr.to_csv("sample_data/products.csv", index=False); rs.to_csv("sample_data/resources.csv", index=False); sf = ["sample_data/products.csv", "sample_data/resources.csv"]
    print("=" * 78); print("SIMUL8 AI starting. Demo data is FICTIONAL. No API key needed."); print("Running self-tests:"); run_selftests(verbose=True); use_data(pr, rs, True); G["custom"] = {}; zp, saved = build_project(); demo = build_ui(zp, sf)
    print("Project ZIP:", zp, "| standalone app.py included:", "yes" if saved else "NO (create app.py yourself by pasting this cell into it)")
    print("Not included / not tested: Streamlit (Gradio used), OR-Tools, PDF export, uploads of your own CSVs. The public Gradio link is open to anyone: do not load confidential data.")
    print("=" * 78); demo.queue().launch(debug=False, show_error=True)
if __name__ == "__main__" or "google.colab" in sys.modules:
    main()