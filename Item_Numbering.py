# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import *
import math

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# -----------------------------------
# GET POINT (robust)
# -----------------------------------
def get_point(el):
    loc = el.Location
    if isinstance(loc, LocationPoint):
        return loc.Point

    bbox = el.get_BoundingBox(None)
    if bbox:
        return (bbox.Min + bbox.Max) * 0.5

    return None

# -----------------------------------
# LOAD DATA
# -----------------------------------
elements = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]

data = []

for el in elements:
    pt = get_point(el)
    if pt:
        data.append({
            "el": el,
            "pt": pt,
            "visited": False
        })

if not data:
    raise Exception("No usable elements selected.")

# -----------------------------------
# HELPERS
# -----------------------------------
def dist_xy(a, b):
    return math.hypot(a.X - b.X, a.Y - b.Y)

def same_xy(a, b):
    return dist_xy(a, b)

# -----------------------------------
# STEP 1: START AT LOWEST
# -----------------------------------
current = min(data, key=lambda x: x["pt"].Z)
current["visited"] = True

ordered = [current]

# -----------------------------------
# MAIN LOOP
# -----------------------------------
while len(ordered) < len(data):

    current_pt = current["pt"]

    # STEP 2: FIND NEXT ABOVE
    candidates = [
        d for d in data
        if not d["visited"] and d["pt"].Z > current_pt.Z
    ]

    next_item = None

    if candidates:
        next_item = min(
            candidates,
            key=lambda d: dist_xy(current_pt, d["pt"])
        )

        sideways_check = [
            d for d in data if not d["visited"]
        ]

        closest_any = min(
            sideways_check,
            key=lambda d: dist_xy(current_pt, d["pt"])
        )

        if dist_xy(current_pt, next_item["pt"]) > dist_xy(current_pt, closest_any["pt"]):
            next_item = None

    # STEP 3: SIDEWAYS
    if next_item is None:
        remaining = [d for d in data if not d["visited"]]

        closest = min(
            remaining,
            key=lambda d: dist_xy(current_pt, d["pt"])
        )

        column_candidates = [
            d for d in remaining
        ]

        column_candidates = [
            d for d in column_candidates
            if abs(dist_xy(d["pt"], closest["pt"])) < 1e-6
        ]

        if not column_candidates:
            column_candidates = [closest]

        next_item = min(column_candidates, key=lambda d: d["pt"].Z)

    # UPDATE
    next_item["visited"] = True
    ordered.append(next_item)
    current = next_item

# -----------------------------------
# WRITE MARKS + COMMENTS
# -----------------------------------
t = Transaction(doc, "Final Stable Numbering")
t.Start()

i = 1
for item in ordered:
    el = item["el"]

    # --- MARK PARAMETER ---
    p = el.LookupParameter("Mark")
    if p and not p.IsReadOnly:
        p.Set(str(i))

    # --- NEW: MODEL IN-PLACE CHECK ---
    try:
        if isinstance(el, FamilyInstance):
            if el.Symbol and el.Symbol.Family.IsInPlace:

                comment_param = el.LookupParameter("Comments")
                if comment_param and not comment_param.IsReadOnly:
                    comment_param.Set("Cut as per site")
    except:
        pass  # safe fallback if element type doesn't support this

    i += 1

t.Commit()

print("✅ Completed with numbering + in-place comments applied.")
