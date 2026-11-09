# Dashboard specification: Tableau Public web authoring (browser, no app)

Four dashboards built from the five CSVs in this folder, entirely in the browser on public.tableau.com. Every field, parameter, calculated field, filter and chart type is listed below, in build order, click by click.

Web authoring menus move occasionally. If a label below differs on screen, the same command is almost always in the **▼** menu on the field or pill, or in the top menu bar (File / Data / Worksheet / Dashboard / Analysis).

## 0. Before you start

### 0.1 Get the CSVs onto your Mac

1. In the VS Code terminal, run `make all` so the CSVs in `tableau/` are fresh.
2. In Finder, open the repo folder, then `tableau/`. Keep this window open; you will drag files from it.

### 0.2 Open the web editor

1. Open Safari or Chrome and go to `public.tableau.com`.
2. Click **Sign In** (top right) and sign in, or create a free account.
3. In the top bar, click **Create**, then **Web Authoring**. (On older layouts: click your profile picture, then **Create a Viz**.)
4. A **Connect to Data** window opens on the **Files** tab.

### 0.3 Connect the five data sources

1. Drag `mart_attrition_lens.csv` from Finder onto the **Connect to Data** window, or click **Upload from computer** and pick it.
2. The data source page opens. Click **Sheet 1** (bottom left) to go to the worksheet.
3. Top menu **Data → New Data Source**. The **Connect to Data** window opens again. Upload `mart_variance_bridge.csv`. Click **Sheet 1**.
4. Repeat step 3 for `mart_orphaned_billing.csv`, `mart_run_rate_resolution.csv` and `mart_source_parity_health.csv`.
5. The Data pane (left) lists the five sources at the top. Click a source name to make it active before you drag its fields.
6. Save early: **File → Save As…**, name the workbook `attrition-lens`, then **Save**. Web authoring has no autosave, so repeat **File → Save** after each section.

### 0.4 How Tableau renames fields

Tableau shows CSV headers in Title Case: `run_rate_eur` appears as **Run Rate Eur**, `dl_tier` as **Dl Tier**. The formulas below use those display names. If a calculation shows a red error, check the exact field name in the Data pane and retype it.

### 0.5 Check field types (once per source)

To change a type, hover the field in the Data pane, click its **▼**, then **Change Data Type**.

| Field | Expected type | How to fix if wrong |
|---|---|---|
| Attrition Year | Number (whole), shown above the grey line (a dimension) | Field **▼ → Convert to Dimension** |
| Departure Date, Last Service Date | Date | Field **▼ → Change Data Type → Date** |
| Is Matched, Is Issue, Caught By Utc Compare | Boolean (T\|F icon) | Field **▼ → Change Data Type → Boolean** |
| Days Since Departure | Number (whole) | Leave as a measure; convert to discrete only where noted |

## 1. Parameters (create once, used across dashboards)

To create each parameter: in the Data pane, click the **▼** next to the search box (or the **▼** on any field), then **Create Parameter…**. Set the values below, then click **OK**. After creating each one, click its **▼** in the Parameters section, then **Show Parameter**.

| Name | Data type | Allowable values | Values (in this order) | Current value |
|---|---|---|---|---|
| `Unit` | String | List | `entity`, `group_any`, `group_full` | `group_any` |
| `Date` | String | List | `status clock`, `contract clock` | `contract clock` |
| `Segment source` | String | List | `Deal Ledger tier`, `BRR tier` | `BRR tier` |
| `Year` | Integer | List | `2023`, `2024`, `2025` | `2025` |
| `Bridge measure` | String | List | `Count`, `Run-rate EUR` | `Count` |

## 2. Dashboard 1: Attrition overview

**Data source:** `mart_attrition_lens`

**Purpose:** pick a counting choice (Unit / Date / Segment source) and watch the same installed base produce a different attrition number.

### 2.1 Calculated fields

In the Data pane, click the **▼** next to the search box, then **Create Calculated Field…** (also under top menu **Analysis**). Type the name, paste the formula, then click **OK**.

| Name | Formula |
|---|---|
| `In selected basis` | `[Unit (field)] = [Unit] AND [Date Basis] = [Date] AND [Segment Source (field)] = [Segment source]` |
| `Is selected year` | `[Attrition Year] = [Year]` |
| `Attrition count` | `SUM([Attrition Count])` |
| `Attrition run-rate EUR` | `SUM([Run Rate Eur])` |
| `Count in Year` | `SUM(IF [Attrition Year] = [Year] THEN [Attrition Count] END)` |
| `Run-rate in Year` | `SUM(IF [Attrition Year] = [Year] THEN [Run Rate Eur] END)` |
| `Count prior year` | `SUM(IF [Attrition Year] = [Year] - 1 THEN [Attrition Count] END)` |
| `Count change vs prior year` | `[Count in Year] - [Count prior year]` |
| `Basis label` | `[Unit] + " / " + [Date] + " / " + [Segment source]` |

**Do this before the formulas: avoid the name clash.** The CSV has fields called `Unit` and `Segment Source`, and you also created parameters with the same names. In the Data pane, click the **▼** on the field **Unit**, then **Rename**, and type `Unit (field)`. Do the same for **Segment Source**, renaming it to `Segment Source (field)`. Leave Date Basis as is.

### 2.2 Sheet "KPI count"

1. Click the **New Worksheet** icon (bottom bar). Double-click the tab and rename it `KPI count`.
2. Drag `In selected basis` to **Filters**, tick **True**, then **OK**.
3. Click the **▼** on the `In selected basis` pill in Filters, then **Add to Context**. It turns grey.
4. Drag `Count in Year` to **Text** on the Marks card.
5. Drag `Basis label` to **Detail**.
6. Click **Text** on the Marks card, then **…**, and edit the text to:

   ```
   Attrition <Year>: <AGG(Count in Year)>
   <ATTR(Basis label)>
   ```

   Set font size 28 for the number line and 10 for the label line, then **OK**.
7. Top toolbar: change **Standard** to **Entire View**.

### 2.3 Sheet "KPI run-rate"

1. Duplicate `KPI count`: Control-click its tab at the bottom, then **Duplicate**. Rename the copy `KPI run-rate`.
2. Drag `Run-rate in Year` onto the `Count in Year` pill on the Marks card to replace it.
3. Click the **▼** on the pill, then **Format Number…**. Choose **Currency (Custom)**, set **Prefix / Suffix** to `EUR `, decimals 0.
4. Edit the text to `Run-rate lost <Year>: <AGG(Run-rate in Year)>`.

### 2.4 Sheet "KPI change"

1. Duplicate `KPI count` again. Rename the copy `KPI change`.
2. Replace the text measure with `Count change vs prior year`.
3. Edit the text to `Change vs <Year>-1: <AGG(Count change vs prior year)>`.
4. Click the **▼** on the pill, then **Format Number… → Custom**, and type `+#,##0;-#,##0;0`.

### 2.5 Sheet "By tier"

1. New worksheet. Rename it `By tier`.
2. Filters: `In selected basis` = True (add to context, as in 2.2).
3. Drag `Is selected year` to **Filters** and tick **True**.
4. Drag **Tier** to **Rows**.
5. Drag `Attrition count` to **Columns**.
6. Marks card dropdown: **Bar**.
7. Drag **Tier** to **Color**.
8. Sort rows in this fixed order: click the **▼** on **Tier** on Rows → **Sort…** → **Manual**, then arrange Anchor, Scale, Standard, Starter.
9. Drag `Attrition count` to **Label**.

### 2.6 Sheet "Trend"

1. New worksheet. Rename it `Trend`.
2. Filters: `In selected basis` = True.
3. Drag **Attrition Year** to **Columns**. Click the **▼** on it and choose **Discrete**.
4. Drag `Attrition count` to **Rows**.
5. Marks card dropdown: **Line**.
6. Drag **Tier** to **Color** (one line per tier).
7. Drag `Attrition count` to **Label**.

### 2.7 Assemble the dashboard

1. Click the **New Dashboard** icon (bottom bar). Rename it `1 Attrition overview`.
2. Left panel **Size**: choose **Automatic**.
3. Drag a **Horizontal** container from **Objects** to the top. Drag `KPI count`, `KPI run-rate` and `KPI change` into it, side by side.
4. Drag `By tier` below the container (left half) and `Trend` beside it (right half).
5. The three parameter controls (`Unit`, `Date`, `Segment source`) and `Year` appear on the right. If they don't: click any sheet on the dashboard, click its **▼** menu, then **Parameters**, and tick each one.
6. For each parameter control: click its **▼** menu and choose **Single Value List** (radio buttons).
7. Add a title: tick **Show dashboard title** at the bottom left. Double-click it and type `Attrition overview: one installed base, many numbers`.

## 3. Dashboard 2: Variance bridge

**Data source:** `mart_variance_bridge`

**Purpose:** a waterfall from Basis A to Basis B. Each step is one reason code. The bars must land exactly on Basis B.

### 3.1 Calculated fields

| Name | Formula |
|---|---|
| `In bridge year` | `[Attrition Year] = [Year]` |
| `Bridge value` | `IF [Bridge measure] = "Count" THEN SUM([Count Delta]) ELSE SUM([Run Rate Eur Delta]) END` |
| `Bridge running total` | `RUNNING_SUM(IF ATTR([Row Type]) = "basis_b" THEN 0 ELSE [Bridge value] END)` |
| `Bridge bar size` | `-[Bridge value]` |
| `Bridge step type` | `CASE [Row Type] WHEN "basis_a" THEN "Basis" WHEN "basis_b" THEN "Basis" WHEN "removal" THEN "Out" WHEN "addition" THEN "In" ELSE "Run-rate only" END` |

**Why this works.** Each Gantt bar starts at the running total and extends back by its own value, so it ends where the previous step ended.

- Basis A starts at A and drops to 0.
- Each movement shifts the running total.
- The Basis B step adds 0 to the running total, which therefore stays at A + movements = B, and the bar drops back to 0. If the bridge did not tie out, the Basis B bar would not line up with the last movement bar.

### 3.2 Sheet "Bridge waterfall"

1. New worksheet. Rename it `Bridge waterfall`.
2. Drag `In bridge year` to **Filters** and tick **True**.
3. Drag **Tier** to **Filters**, keep all values ticked, then click **OK**. Click the **▼** on it and choose **Show Filter**.
4. Drag **Step Label** to **Columns**. It sorts alphabetically, and the leading digit gives the right order (0 Basis A … 9 Basis B).
5. Drag `Bridge running total` to **Rows**.
6. Click the **▼** on the `Bridge running total` pill, then **Compute Using → Step Label**.
7. Marks card dropdown: **Gantt Bar**.
8. Drag `Bridge bar size` to **Size**.
9. Drag `Bridge step type` to **Color**. Click **Color → Edit Colors…** and assign: Basis = dark grey, Out = red, In = green, Run-rate only = amber.
10. Drag `Bridge value` to **Label**.
11. If the step labels overlap, set the fit dropdown in the toolbar to **Fit Width**.

### 3.3 Sheet "Bridge detail"

1. New worksheet. Rename it `Bridge detail`.
2. Filters: `In bridge year` = True. Then **Row Type**: tick only `removal`, `addition`, `amount_only`.
3. Drag **Step Label**, **Group Id**, **Tier** and **Detail** to **Rows**, in that order.
4. Drag **Count Delta** and **Run Rate Eur Delta** onto the table body (**Text**). Tableau creates Measure Names / Measure Values automatically.
5. Rows are sortable: hover a column header and click the sort icon.

### 3.4 Assemble the dashboard

1. New Dashboard. Rename it `2 Variance bridge`.
2. Drag `Bridge waterfall` to the top (about 60% of the height). Drag `Bridge detail` below it.
3. Show the `Year` and `Bridge measure` parameter controls, and the `Tier` filter.
4. Click the `Bridge waterfall` sheet on the dashboard, then the funnel icon (**Use as Filter**). Clicking a step now filters the detail table to that step's groups.
5. Title: `Variance bridge: Basis A to Basis B`. Add a **Text** object under the title and type:

   ```
   Basis A: entity, status clock, Deal Ledger tier, member entities excluded.
   Basis B: group_any, contract clock, BRR tier, entity transfers excluded.
   ```

## 4. Dashboard 3: Orphaned billing

**Data source:** `mart_orphaned_billing`

**Purpose:** Departed entities that Billing Core still bills, ranked by MRR at risk.

### 4.1 Calculated fields

| Name | Formula |
|---|---|
| `Tier (selected source)` | `IF [Segment source] = "BRR tier" THEN [Brr Tier] ELSE [Dl Tier] END` |
| `MRR at risk` | `SUM([Mrr At Risk Eur])` |
| `Orphaned entities` | `COUNTD([Entity Id])` |
| `Missed by UTC compare` | `SUM(IF [Caught By Utc Compare] THEN 0 ELSE 1 END)` |

### 4.2 Sheet "Orphan list"

1. New worksheet. Rename it `Orphan list`.
2. Drag to **Rows**, in order: **Entity Id**, **Orphan Type**, `Tier (selected source)`, **Departure Date**, **Link Path**, **Caught By Utc Compare**.
3. Click the **▼** on **Departure Date** on Rows, then **Exact Date**, then **Discrete**.
4. Drag **Days Since Departure** to Rows, then click the **▼** on it and choose **Dimension**, then **Discrete**.
5. Drag `MRR at risk` to **Text**.
6. Sort: click the **▼** on the `Entity Id` pill, then **Sort… → Field → MRR at risk → Descending**. Viewers can re-sort by clicking any header's sort icon.

### 4.3 Sheet "MRR at risk by tier"

1. New worksheet. Rename it `MRR at risk by tier`.
2. Drag `Tier (selected source)` to **Rows** and `MRR at risk` to **Columns**.
3. Drag **Orphan Type** to **Color**. The bars stack active_plan and post_departure_invoice.
4. Drag `MRR at risk` to **Label**.
5. Format the axis and labels: click the **▼** on the `MRR at risk` pill, then **Format Number… → Currency (Custom)**, with prefix `EUR `.

### 4.4 KPI sheets

Duplicate the technique from 2.2: one sheet per KPI, each with a single measure on **Text**, set to **Entire View**.

- `KPI orphaned entities` uses `Orphaned entities`.
- `KPI MRR at risk` uses `MRR at risk`.
- `KPI missed by UTC` uses `Missed by UTC compare`. Use the text `Missed by a UTC date compare: <AGG(Missed by UTC compare)>`.

### 4.5 Assemble the dashboard

1. New Dashboard. Rename it `3 Orphaned billing`.
2. Put the three KPI sheets in a horizontal container at the top.
3. Put `MRR at risk by tier` on the left and `Orphan list` on the right.
4. Show the `Segment source` parameter control.
5. Use `MRR at risk by tier` as a filter (funnel icon), so a tier click filters the list.
6. Title: `Orphaned billing: departed, still billing`.

## 5. Dashboard 4: Source parity health

**Data sources:** `mart_source_parity_health` and `mart_run_rate_resolution`

**Purpose:** how well the five systems join, and where they don't.

### 5.1 Calculated fields (on `mart_source_parity_health`)

| Name | Formula |
|---|---|
| `Match rate` | `SUM(INT([Is Matched])) / COUNT([Parity Row Id])` |
| `Issue count` | `SUM(INT([Is Issue]))` |
| `Rows` | `COUNT([Parity Row Id])` |

### 5.2 Sheet "Match rates"

1. New worksheet. Rename it `Match rates`.
2. Drag **Check Name** to **Filters**. Tick only `billing_link`, `brr_run_rate`, `engagement_link` and `partner_biller_gap`.
3. Drag **Source System** then **Check Name** to **Rows**.
4. Drag `Match rate` to **Columns**. Click the **▼** on the pill, then **Format Number… → Percentage**, 1 decimal.
5. Marks: **Bar**. Drag `Match rate` to **Label**. Drag `Rows` to **Tooltip**.
6. Click the `Match rate` axis, then **Edit Axis…**, and set a fixed range from 0 to 1.

### 5.3 Sheet "Billing link paths"

1. New worksheet. Rename it `Billing link paths`.
2. Filter **Check Name** = `billing_link`.
3. Drag **Outcome** to **Rows** and `Rows` to **Columns**. Marks: **Bar**. Drag `Rows` to **Label**.

   This shows how many entities link by direct_ref, comma_list, crosswalk and crosswalk_semicolon.

### 5.4 Sheet "Partner Biller gaps"

1. New worksheet. Rename it `Partner Biller gaps`.
2. Filter **Check Name** = `partner_biller_gap`.
3. Drag **Subject Id**, **Entity Id**, **Outcome** and **Detail** to **Rows**. Detail holds the region.
4. Drag `Rows` to **Text**.

### 5.5 Sheet "Duplicate contacts"

1. New worksheet. Rename it `Duplicate contacts`.
2. Filter **Check Name** = `duplicate_contact`.
3. Drag **Entity Id**, **Subject Id**, **Outcome** and **Detail** to **Rows**. Detail holds the keeper ID and the activity score.
4. Drag **Outcome** to **Color**. Click **Color → Edit Colors…** and set keep = green, delete = red.
5. Drag `Rows` to **Text**.

### 5.6 Sheet "Clock-boundary misses"

1. New worksheet. Rename it `Clock-boundary misses`.
2. Filter **Check Name** = `clock_boundary`.
3. Drag **Subject Id**, **Entity Id** and **Detail** to **Rows**. Detail holds the UTC time, the local date and the departure date.
4. Drag `Rows` to **Text**.
5. For the KPI: duplicate the sheet, remove all pills from Rows, keep `Rows` on **Text**, set **Entire View**, and edit the text to `Invoices missed by a UTC compare: <AGG(Rows)>`. Rename it `KPI clock boundary`.

### 5.7 Sheet "Run-rate lookup" (data source `mart_run_rate_resolution`)

1. Click `mart_run_rate_resolution` in the Data pane to make it active. New worksheet. Rename it `Run-rate lookup`.
2. Drag **Resolution Outcome** to **Rows**.
3. Drag **Entity Id** to **Columns**. Click the **▼** on the pill, then **Measure → Count (Distinct)**.
4. Marks: **Bar**. Drag **Resolution Outcome** to **Color**. Drag **CNTD(Entity Id)** to **Label**.

   Reading: `naive_match` = found by the Deal Ledger ID alone; `resolved_via_billing_key` = blank under the naive lookup, found through the crosswalk; `partner_biller_no_brr` = blank under both.

### 5.8 Assemble the dashboard

1. New Dashboard. Rename it `4 Source parity health`.
2. Top row (horizontal container): `Match rates` and `KPI clock boundary`.
3. Middle row: `Billing link paths` and `Run-rate lookup`.
4. Bottom row: `Partner Biller gaps`, `Duplicate contacts` and `Clock-boundary misses`.
5. Title: `Source parity health`.

## 6. Publish

1. Top menu **File → Save** (the workbook was named `attrition-lens` in 0.3).
2. Click **Close** (top right of the editor) to see the published workbook page.
3. Copy the URL from the browser address bar and paste it into the README under **Dashboards**.
4. For screenshots, open each dashboard tab on the published page, then press **Cmd+Shift+4**, then **Space**, then click the browser window. The PNG lands on your Desktop.
5. In the terminal, create the image folder and move the files in (adjust the file names to what macOS saved):

```bash
mkdir -p docs/img
mv ~/Desktop/Screenshot*.png docs/img/
ls docs/img
```

6. Rename them to `1-attrition-overview.png`, `2-variance-bridge.png`, `3-orphaned-billing.png` and `4-source-parity-health.png`, then reference them in the README.
