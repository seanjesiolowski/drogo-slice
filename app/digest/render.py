from datetime import date

_TEMPLATE = """\
<!doctype html>
<html>
  <body style="font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; color: #222; max-width: 600px; margin: 0 auto; padding: 24px;">
    <h1 style="font-size: 22px; margin: 0 0 4px 0;">Drogo Slice — Weekly Digest</h1>
    <p style="color: #666; margin: 0 0 24px 0;">{week_of}</p>

    <h2 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #666; margin: 0 0 8px 0;">Inventory totals (all items)</h2>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
      <tr>
        <td style="padding: 12px; background: #fef2f2; border-radius: 6px;">
          <div style="color: #991b1b; font-size: 12px; text-transform: uppercase;">Critical</div>
          <div style="font-size: 28px; font-weight: 600; color: #991b1b;">{critical_count}</div>
        </td>
        <td style="width: 8px;"></td>
        <td style="padding: 12px; background: #fffbeb; border-radius: 6px;">
          <div style="color: #92400e; font-size: 12px; text-transform: uppercase;">Low</div>
          <div style="font-size: 28px; font-weight: 600; color: #92400e;">{low_count}</div>
        </td>
        <td style="width: 8px;"></td>
        <td style="padding: 12px; background: #f0fdf4; border-radius: 6px;">
          <div style="color: #166534; font-size: 12px; text-transform: uppercase;">OK</div>
          <div style="font-size: 28px; font-weight: 600; color: #166534;">{ok_count}</div>
        </td>
      </tr>
    </table>

    <h2 style="font-size: 16px; margin: 0 0 8px 0;">Needs attention (critical &amp; low)</h2>
    <table style="width: 100%; border-collapse: collapse;">
      <thead>
        <tr style="text-align: left; border-bottom: 1px solid #e5e7eb;">
          <th style="padding: 8px 4px; font-size: 12px; color: #666;">Item</th>
          <th style="padding: 8px 4px; font-size: 12px; color: #666;">Category</th>
          <th style="padding: 8px 4px; font-size: 12px; color: #666;">Qty / Par</th>
          <th style="padding: 8px 4px; font-size: 12px; color: #666;">Status</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </body>
</html>
"""

_ROW = """\
<tr style="border-bottom: 1px solid #f3f4f6;">
  <td style="padding: 8px 4px;">{name}</td>
  <td style="padding: 8px 4px; color: #666;">{category}</td>
  <td style="padding: 8px 4px;">{current} / {par} {unit}</td>
  <td style="padding: 8px 4px;"><span style="color: {color}; font-weight: 600;">{status}</span></td>
</tr>"""

_STATUS_COLOR = {"critical": "#991b1b", "low": "#92400e", "ok": "#166534"}


def render_digest(week_of: date, items: list[dict], totals: dict[str, int]) -> str:
    rows = "\n        ".join(
        _ROW.format(
            name=i["name"],
            category=i["category"],
            current=i["current"],
            par=i["par"],
            unit=i["unit"],
            status=i["status"],
            color=_STATUS_COLOR.get(i["status"], "#222"),
        )
        for i in items
    ) or '<tr><td colspan="4" style="padding: 12px; color: #666;">Nothing to flag.</td></tr>'

    return _TEMPLATE.format(
        week_of=week_of.strftime("Week of %B %d, %Y"),
        critical_count=totals.get("critical", 0),
        low_count=totals.get("low", 0),
        ok_count=totals.get("ok", 0),
        rows=rows,
    )
