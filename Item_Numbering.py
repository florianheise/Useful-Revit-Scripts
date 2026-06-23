# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import *
import math

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

# -----------------------------------
# GET POINT
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
# HELPERS
# -----------------------------------
def avg_point(group):
    total = XYZ(0, 0, 0)
    for d in group:
        total += d["pt"]
    return total / len(group)

def dist_xy(a, b):
    return math.hypot(a.X - b.X, a.Y - b.Y)

# -----------------------------------
# LOAD DATA
# -----------------------------------
elements = [doc.GetElement(i) for i in uidoc.Selection.GetElementIds()]

data = []
for el in elements:
    pt = get_point(el)
    if pt:
        data.append({"el": el, "pt": pt})

if not data:
    raise Exception("No usable elements selected.")

# -----------------------------------
# SETTINGS
# -----------------------------------
GRID_COL = 0.1
GRID_DEPTH = 0.3

# -----------------------------------
# STEP 1: DETERMINE ORIENTATION
# -----------------------------------
xs = [d["pt"].X for d in data]
ys = [d["pt"].Y for d in data]

range_x = max(xs) - min(xs)
range_y = max(ys) - min(ys)

use_x_for_columns = range_x > range_y

# -----------------------------------
# STEP 2: NORMALISE ORIGIN
# -----------------------------------
min_x = min(xs)
min_y = min(ys)

# -----------------------------------
# STEP 3: ASSIGN COLUMN + PLANE
# -----------------------------------
for d in data:
    pt = d["pt"]

    if use_x_for_columns:
        d["col"] = int(round((pt.X - min_x) / GRID_COL))
        d["plane"] = int(round((pt.Y - min_y) / GRID_DEPTH))
    else:
        d["col"] = int(round((pt.Y - min_y) / GRID_COL))
        d["plane"] = int(round((pt.X - min_x) / GRID_DEPTH))

# -----------------------------------
# STEP 4: GROUP COLUMNS
# -----------------------------------
columns = {}
for d in data:
    columns.setdefault(d["col"], []).append(d)

col_keys = list(columns.keys())

# -----------------------------------
# STEP 5: FIND START COLUMN (BOTTOM LEFT)
# -----------------------------------
def column_score(col):
    pts = columns[col]
    min_z = min(d["pt"].Z for d in pts)
    avg = avg_point(pts)
    return (min_z, avg.X + avg.Y)

start_col = min(col_keys, key=column_score)

# -----------------------------------
# STEP 6: ADJACENT COLUMN WALK
# -----------------------------------
ordered_cols = [start_col]
remaining = set(col_keys)
remaining.remove(start_col)

current = start_col

while remaining:
    current_center = avg_point(columns[current])

    next_col = min(
        remaining,
        key=lambda c: dist_xy(current_center, avg_point(columns[c]))
    )

    ordered_cols.append(next_col)
    remaining.remove(next_col)
    current = next_col

# -----------------------------------
# STEP 7: PROCESS EACH COLUMN
# plane → height
# -----------------------------------
ordered = []

for col in ordered_cols:
    items = columns[col]

    # group planes
    planes = {}
    for d in items:
        planes.setdefault(d["plane"], []).append(d)

    # sort planes
    for p in sorted(planes.keys()):
        plane_items = planes[p]

        # ✅ always bottom → top
        plane_sorted = sorted(plane_items, key=lambda d: d["pt"].Z)

        ordered.extend(plane_sorted)

# -----------------------------------
# WRITE RESULTS
# -----------------------------------
t = Transaction(doc, "Final Adjacency Locked Numbering")
t.Start()

i = 1
for item in ordered:
    el = item["el"]

    p = el.LookupParameter("Mark")
    if p and not p.IsReadOnly:
        p.Set(str(i))

    try:
        if isinstance(el, FamilyInstance):
            if el.Symbol and el.Symbol.Family.IsInPlace:
                c = el.LookupParameter("Comments")
                if c and not c.IsReadOnly:
                    c.Set("Cut as per site")
    except:
        pass

    i += 1

t.Commit()

print("✅ Completed: Fully adjacency-locked column sweep.")
