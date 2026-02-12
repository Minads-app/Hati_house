import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta

from src.db import get_completed_bookings, get_all_rooms, get_all_room_types
from src.models import Permission
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, require_permission, has_permission

st.set_page_config(page_title="Báo cáo doanh thu", layout="wide")

require_login()
require_permission(Permission.VIEW_FINANCE)

apply_sidebar_style()
create_custom_sidebar_menu()
st.title("📊 Finance - Báo cáo doanh thu")

# --- ACTION BUTTONS (Moved Up) ---
c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
st.caption("Nguồn dữ liệu: collection `bookings` (chỉ tính các booking đã trả phòng / có `check_out_actual`).")

# Placeholder for Metrics (Top of Page)
metrics_container = st.container()
with st.container(border=True):
    # Sử dụng 4 cột trên 1 hàng để tiết kiệm diện tích dọc
    c_preset, c_from, c_to, c_group = st.columns([1.5, 1, 1, 1])

    with c_preset:
        preset = st.selectbox(
            "Khoảng thời gian",
            ["Hôm nay", "7 ngày gần nhất", "Tháng này", "Tháng trước", "Tùy chọn"],
            index=1, # Default 7 ngày
        )

    # Logic tính ngày
    today = date.today()
    if preset == "Hôm nay":
        start_d, end_d = today, today
    elif preset == "7 ngày gần nhất":
        start_d, end_d = today - timedelta(days=6), today
    elif preset == "Tháng này":
        start_d, end_d = today.replace(day=1), today
    elif preset == "Tháng trước":
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        start_d, end_d = last_prev_month.replace(day=1), last_prev_month
    else:
        start_d, end_d = today.replace(day=1), today

    with c_from:
        disable_date = (preset != "Tùy chọn")
        d_from = st.date_input("Từ ngày", value=start_d, format="DD/MM/YYYY", disabled=disable_date)

    with c_to:
        d_to = st.date_input("Đến ngày", value=end_d, format="DD/MM/YYYY", disabled=disable_date)
    
    with c_group:
        group_mode = st.radio("Nhóm theo", ["Ngày", "Tháng"], horizontal=True)

# --- 2. DATA FETCHING & PROCESSING ---
start_dt = datetime.combine(d_from, time.min)
end_dt = datetime.combine(d_to, time.max)
bookings = get_completed_bookings(start_dt=start_dt, end_dt=end_dt)

# Fetch Metadata
rooms = get_all_rooms()
room_types = get_all_room_types()
room_map = {r.get("id"): r for r in rooms}
type_map = {t.get("type_code"): t for t in room_types}

rows = []
total_rev = 0.0
room_rev = 0.0
service_rev = 0.0
# Set for counting unique guests
unique_guests = set()
missing_ts = 0

def _safe_dt(x):
    if isinstance(x, datetime): return x.replace(tzinfo=None)
    return None

for b in bookings:
    out_actual = _safe_dt(b.get("check_out_actual"))
    if out_actual is None:
        missing_ts += 1
        continue

    # Amounts
    total = float(b.get("total_amount") or b.get("price_original") or 0.0)
    svc = float(b.get("service_fee") or 0.0)
    rf = total - svc
    
    total_rev += total
    service_rev += svc
    room_rev += rf

    # Guests
    c_name = b.get("customer_name", "").strip()
    if c_name:
        unique_guests.add(c_name)

    # Info
    room_id = b.get("room_id", "")
    t_code = b.get("room_type_code", "")
    t_name = type_map.get(t_code, {}).get("name", t_code)

    rows.append({
        "booking_id": b.get("id") or b.get("booking_id") or "",
        "room_id": room_id,
        "room_type_name": t_name,
        "customer_name": c_name,
        "check_in": _safe_dt(b.get("check_in")),
        "check_out_actual": out_actual,
        "total_amount": total,
        "service_fee": svc,
        "payment_method": b.get("payment_method") or "Chưa rõ",
        "note": b.get("note", ""),
    })

df = pd.DataFrame(rows)
num_bills = len(df)
num_guests = len(unique_guests)

# --- 3. DISPLAY METRICS (In Top Placeholder) ---
with metrics_container:
    # Chia cột theo tỷ lệ: Doanh thu rộng hơn, số lượng hẹp lại
    m1, m2, m3, m4, m5 = st.columns([1.5, 0.8, 0.8, 1.5, 1.5])
    m1.metric("Tổng doanh thu", f"{total_rev:,.0f} đ", delta_color="off")
    m2.metric("Tổng số bill", f"{num_bills}")
    m3.metric("Tổng khách thuê", f"{num_guests}")
    m4.metric("Doanh thu phòng", f"{room_rev:,.0f} đ")
    m5.metric("Doanh thu dịch vụ", f"{service_rev:,.0f} đ")
    st.divider()

# --- 4. ACTION BUTTONS & DETAILED TABLE ---
# Yêu cầu: Tổng doanh thu, tổng bill, tổng khách thuê, doanh thu phòng, doanh thu dịch vụ
# Metrics moved to top container

st.divider()

# --- 4. ACTION BUTTONS & DETAILED TABLE ---
c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])

# Display Data Handling
display_rows = []
if not df.empty:
    for idx, row in enumerate(rows):
         display_rows.append({
            "STT": idx + 1,
            "Thời gian Check-in": row["check_in"].strftime("%d/%m/%Y %H:%M") if row["check_in"] else "",
            "Thời gian Check-out": row["check_out_actual"].strftime("%d/%m/%Y %H:%M") if row["check_out_actual"] else "",
            "Mã Bill": row["booking_id"],
            "Phòng": row["room_id"],
            "Tiền dịch vụ": row["service_fee"],
            "Tên khách hàng": row["customer_name"],
            "Số tiền": row["total_amount"],
            "Phương thức": row["payment_method"],
            "Ghi chú": row["note"]
         })
    df_display = pd.DataFrame(display_rows)
else:
    df_display = pd.DataFrame(columns=["STT", "Thời gian Check-in", "Thời gian Check-out", "Mã Bill", "Phòng", "Tiền dịch vụ", "Tên khách hàng", "Số tiền", "Phương thức", "Ghi chú"])

# Buttons
if has_permission(Permission.EXPORT_REPORTS):
    csv_data = df_display.to_csv(index=False).encode("utf-8-sig")
    c_btn2.download_button(
        "📥 Xuất Excel (.csv)",
        data=csv_data,
        file_name=f"DoanhThu_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=df.empty
    )
else:
    c_btn2.button("📥 Xuất Excel (.csv)", disabled=True, key="btn_export_disabled", help="Bạn không có quyền xuất báo cáo")


# Print Logic
def generate_print_html(dataframe, d_s, d_e):
    html_rows = ""
    for _, r in dataframe.iterrows():
        html_rows += f"<tr><td>{r['STT']}</td><td>{r['Thời gian Check-in']}</td><td>{r['Thời gian Check-out']}</td>"
        html_rows += f"<td>{r['Mã Bill']}</td><td>{r['Phòng']}</td><td class='right'>{r['Tiền dịch vụ']:,.0f}</td>"
        html_rows += f"<td>{r['Tên khách hàng']}</td><td class='right'><b>{r['Số tiền']:,.0f}</b></td>"
        html_rows += f"<td>{r['Phương thức']}</td><td>{r['Ghi chú']}</td></tr>"
    return f"""<html><head><style>
        body{{font-family:Arial,sans-serif;padding:20px}} h2,h4{{text-align:center}} table{{width:100%;border-collapse:collapse;font-size:12px}}
        th,td{{border:1px solid #ddd;padding:5px}} th{{background:#eee}} .right{{text-align:right}}
        @media print{{@page{{size:A4 landscape;margin:10mm}} body{{padding:0}}}}
    </style></head><body onload="window.print()">
    <h2>BÁO CÁO DOANH THU</h2><h4>{d_s.strftime('%d/%m/%Y')} - {d_e.strftime('%d/%m/%Y')}</h4>
    <table><thead><tr><th>STT</th><th>In</th><th>Out</th><th>Bill</th><th>Phòng</th><th>Dịch vụ</th><th>Khách</th><th>Tổng</th><th>PTTT</th><th>Note</th></tr></thead>
    <tbody>{html_rows}</tbody></table></body></html>"""

import streamlit.components.v1 as components
if has_permission(Permission.EXPORT_REPORTS):
    if not df.empty and c_btn3.button("🖨️ In Báo Cáo", use_container_width=True):
        html = generate_print_html(df_display, d_from, d_to)
        components.html(html, height=0, width=0)
else:
    c_btn3.button("🖨️ In Báo Cáo", disabled=True, key="btn_print_disabled")

if c_btn1.button("👁️ Xem / Làm mới", use_container_width=True):
    st.rerun()

# --- TABLE DISPLAY ---
st.subheader(f"📄 Chi tiết doanh thu {d_from.strftime('%d/%m/%Y')} - {d_to.strftime('%d/%m/%Y')}")

if df.empty:
    st.info("Không có dữ liệu trong khoảng thời gian này.")
else:
    st.dataframe(
        df_display, 
        column_config={
            "STT": st.column_config.NumberColumn("STT", width="small"),
            "Tiền dịch vụ": st.column_config.NumberColumn("Tiền dịch vụ", format="%d đ"),
            "Số tiền": st.column_config.NumberColumn("Số tiền", format="%d đ"),
        },
        use_container_width=True, 
        hide_index=True,
        height=300
    )

# --- CHARTS (If Data Exists) ---
if not df.empty:
    st.divider()
    df = df.sort_values("check_out_actual")
    df["date"] = df["check_out_actual"].dt.date
    df["month"] = df["check_out_actual"].dt.to_period("M").astype(str)

    group_key = "date" if group_mode == "Ngày" else "month"
    ts = df.groupby(group_key, as_index=False)["total_amount"].sum().rename(columns={"total_amount": "revenue"})

    col_chart, col_top = st.columns([1.6, 1])
    with col_chart:
        st.subheader("Biểu đồ doanh thu")
        st.line_chart(ts.set_index(group_key)["revenue"])

    with col_top:
        st.subheader("Top phòng doanh thu cao")
        top_rooms = (
            df.groupby("room_id", as_index=False)["total_amount"]
            .sum()
            .sort_values("total_amount", ascending=False)
            .head(10)
            .rename(columns={"total_amount": "revenue"})
        )
        st.dataframe(
            top_rooms, 
            column_config={
                "room_id": "Phòng",
                "revenue": st.column_config.NumberColumn("Doanh thu", format="%d đ")
            },
            use_container_width=True, 
            hide_index=True
        )

if missing_ts > 0:
    st.caption(f"Ghi chú: có {missing_ts} booking thiếu `check_out_actual` nên đã bị loại khỏi báo cáo.")