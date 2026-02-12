import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components
from html import escape
from urllib.parse import quote_plus
from src.db import (
    get_occupied_rooms,
    get_booking_by_id,
    process_checkout,
    get_all_room_types,
    update_room_status,
    get_payment_config,
    calculate_service_total,
    get_orders_by_booking,
)
from src.models import RoomStatus, Permission
from src.logic import calculate_estimated_price, BookingType
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, require_permission, has_permission

st.set_page_config(page_title="Trả phòng & Thanh toán", layout="wide")

require_login()
require_permission(Permission.CHECKIN_CHECKOUT)

apply_sidebar_style()
create_custom_sidebar_menu()

st.title("💸 Trả phòng & Thanh toán")

# --- STATE: MÀN HÌNH HÓA ĐƠN SAU THANH TOÁN ---
if "checkout_success_data" not in st.session_state:
    st.session_state["checkout_success_data"] = None
if "checkout_print_now" not in st.session_state:
    st.session_state["checkout_print_now"] = False

def _money(x: float) -> str:
    try:
        return f"{float(x):,.0f}"
    except Exception:
        return "0"

def _fmt_dt(dt: datetime | None) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M")
    return ""

def _render_bill_html(data: dict, auto_print: bool = False, print_format: str = "A5") -> str:
    # Escape các trường text tự do để tránh lỗi HTML
    note = escape(str(data.get("note", "") or ""))
    payment_method = escape(str(data.get("payment_method", "") or ""))

    script = ""
    if auto_print:
        # In trong iframe (đa số trình duyệt vẫn mở dialog in)
        script = "<script>window.onload=function(){setTimeout(function(){window.print();}, 250);};</script>"

    # Thông tin tài khoản thanh toán (nếu có)
    pay_cfg = get_payment_config()
    bank_block = ""
    qr_block = ""
    if pay_cfg:
        bank_line = ""
        if pay_cfg.get("bank_name") or pay_cfg.get("account_number"):
            bank_line = f"{escape(pay_cfg.get('bank_name',''))} - STK: {escape(pay_cfg.get('account_number',''))} ({escape(pay_cfg.get('account_name',''))})"
        note_line = escape(pay_cfg.get("note", ""))

        bank_block = f"""
        <div class="line"></div>
        <div><b>Thông tin chuyển khoản:</b><br/>{bank_line}<br/>{note_line}</div>
        """

        # Chỉ hiển thị QR trên bill nếu thanh toán bằng chuyển khoản
        bank_id = pay_cfg.get("bank_id")
        acc_no = pay_cfg.get("account_number")
        if "chuyển khoản" in payment_method.lower() and bank_id and acc_no:
            # Số tiền cần thanh toán (VND) truyền vào VietQR
            amount_vnd = int(float(data.get("final_payment", 0) or 0))
            qr_url = (
                f"https://img.vietqr.io/image/"
                f"{bank_id}-{acc_no}-compact2.png?"
                f"accountName={quote_plus(pay_cfg.get('account_name',''))}&"
                f"addInfo={quote_plus(pay_cfg.get('note','Thanh toan tien phong'))}&"
                f"amount={amount_vnd}"
            )
            qr_block = f"""
            <div style=\"margin-top: 10px; text-align:center;\">
              <img src=\"{qr_url}\" alt=\"QR thanh toán\" style=\"max-width:220px;\"/>
            </div>
            """

    # CSS Configuration based on Print Format
    if print_format == "K80":
        # Bill in nhiệt K80 (80mm) -> Content max-width ~72mm
        page_style = """
            @page { size: auto; margin: 0mm; }
            body { 
                font-family: 'Courier New', monospace; 
                font-size: 11px; 
                margin: 0; 
                padding: 10px 5px; 
                width: 72mm; /* Safe width for 80mm paper */
            }
            .bill { border: none; padding: 0; width: 100%; }
            h2 { font-size: 14px; margin-bottom: 5px; }
            .muted { font-size: 10px; margin-bottom: 8px; }
            td { padding: 2px 0; border-bottom: 1px dashed #333; }
            .line { margin: 5px 0; border-top: 1px dashed #000; }
            .total { font-size: 14px; }
        """
    else:
        # Bill A5 (148mm x 210mm) -> Content responsive but optimized for A5
        page_style = """
            @page { size: A5 portrait; margin: 10mm; }
            body { font-family: Arial, sans-serif; padding: 16px; font-size: 13px; }
            .bill { max-width: 100%; margin: 0 auto; border: 1px dashed #999; padding: 16px; border-radius: 10px; }
            h2 { margin: 0 0 8px 0; text-align: center; }
            .muted { color: #666; font-size: 12px; text-align: center; margin-bottom: 12px; }
            table { width: 100%; border-collapse: collapse; }
            td { padding: 6px 0; vertical-align: top; border-bottom: 1px solid #eee; }
            .right { text-align: right; }
            .line { border-top: 1px solid #ddd; margin: 10px 0; }
            .total { font-size: 18px; font-weight: bold; }
            
            @media print {
                body { padding: 0; }
                .bill { border: none; padding: 0; }
            }
        """

    return f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <style>
        {page_style}
        /* Common Utils */
        table {{ width: 100%; border-collapse: collapse; }}
        .right {{ text-align: right; }}
        .hide-print {{ display: none; }}
      </style>
    </head>
    <body>
      <div class="bill">
        <h2>THE BAMBOO RESORT</h2>
        <div class="muted">HÓA ĐƠN THANH TOÁN</div>

        <table>
          <tr><td><b>Phòng</b></td><td class="right">{escape(str(data.get("room_id","")))}</td></tr>
          <tr><td><b>Khách</b></td><td class="right">{escape(str(data.get("customer_name","")))}</td></tr>
          <tr><td><b>SĐT</b></td><td class="right">{escape(str(data.get("customer_phone","")))}</td></tr>
          <tr><td><b>Check-in</b></td><td class="right">{escape(_fmt_dt(data.get("check_in")))}</td></tr>
          <tr><td><b>Check-out</b></td><td class="right">{escape(_fmt_dt(data.get("check_out")))}</td></tr>
        </table>

        <div class="line"></div>

        <table>
          <tr><td>Tiền phòng</td><td class="right">{_money(data.get("room_fee",0))} đ</td></tr>
          <tr><td>Dịch vụ / Phụ thu</td><td class="right">{_money(data.get("service_fee",0))} đ</td></tr>
          {f'<tr><td>Giảm giá</td><td class="right">-{_money(data.get("discount",0))} đ</td></tr>' if data.get('discount', 0) > 0 else ''}
          <tr><td><b>Tổng cộng</b></td><td class="right"><b>{_money(data.get("total_gross",0))} đ</b></td></tr>
          <tr><td>Đã cọc</td><td class="right">-{_money(data.get("deposit",0))} đ</td></tr>
          <tr><td class="total">Khách trả</td><td class="right total">{_money(data.get("final_payment",0))} đ</td></tr>
        </table>

        <div class="line"></div>

        <table>
          <tr><td><b>Thanh toán</b></td><td class="right">{payment_method}</td></tr>
          <tr><td><b>Ghi chú</b></td><td class="right">{note}</td></tr>
        </table>

        <div class="line"></div>
        {bank_block}
        {qr_block}
        <div class="muted">Cảm ơn quý khách!<br/>Hẹn gặp lại!</div>
      </div>
      {script}
    </body>
    </html>
    """

def reset_page():
    st.session_state["checkout_success_data"] = None
    st.session_state["checkout_print_now"] = False
    st.rerun()

# === MÀN HÌNH: HÓA ĐƠN SAU KHI THANH TOÁN THÀNH CÔNG ===
if st.session_state["checkout_success_data"]:
    data = st.session_state["checkout_success_data"]

    st.balloons()
    st.title("✅ Thanh toán thành công!")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.subheader("🧾 Hóa đơn")
        st.markdown(
            f"""
            <div style="background-color:#f0f2f6; padding:16px; border-radius:10px; border:1px dashed #ccc;">
              <p><b>Phòng:</b> {data.get('room_id','')}</p>
              <p><b>Khách:</b> {data.get('customer_name','')} ({data.get('customer_phone','')})</p>
              <hr>
              <p><b>Check-in:</b> {_fmt_dt(data.get('check_in'))}</p>
              <p><b>Check-out:</b> {_fmt_dt(data.get('check_out'))}</p>
              <hr>
              <p><b>Tiền phòng:</b> {_money(data.get('room_fee',0))} đ</p>
              <p><b>Dịch vụ/phụ thu:</b> {_money(data.get('service_fee',0))} đ</p>
              {f"<p><b>Giảm giá:</b> -{_money(data.get('discount',0))} đ</p>" if data.get('discount', 0) > 0 else ''}
              <p><b>Tổng cộng:</b> {_money(data.get('total_gross',0))} đ</p>
              <p><b>Đã cọc:</b> -{_money(data.get('deposit',0))} đ</p>
              <p style="font-size:18px;"><b>KHÁCH CẦN TRẢ:</b> {_money(data.get('final_payment',0))} đ</p>
              <p><b>Thanh toán:</b> {data.get('payment_method','')}</p>
              <p><b>Ghi chú:</b> {escape(str(data.get('note','') or ''))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Lựa chọn khổ giấy in
        print_fmt = st.radio("🖨️ Chọn khổ giấy in:", ["A5", "K80"], index=0, horizontal=True)

        b1, b2, b3 = st.columns([1, 1, 1])
        if b1.button("🖨️ In bill ngay", type="primary", use_container_width=True):
            st.session_state["checkout_print_now"] = True
            st.session_state["checkout_print_fmt"] = print_fmt # Lưu lại khổ giấy đã chọn
            st.rerun()

        # Generate HTML based on selected format for download
        html_bill = _render_bill_html(data, auto_print=False, print_format=print_fmt).encode("utf-8")
        b2.download_button(
            f"⬇️ Tải bill ({print_fmt})",
            data=html_bill,
            file_name=f"bill_{data.get('room_id','')}_{datetime.now().strftime('%Y%m%d_%H%M')}_{print_fmt}.html",
            mime="text/html",
            use_container_width=True,
        )

        if b3.button("⬅️ Quay lại", use_container_width=True):
            reset_page()

        # Nếu user bấm in: render HTML + auto print
        if st.session_state.get("checkout_print_now"):
            st.session_state["checkout_print_now"] = False
            # Lấy khổ giấy từ session (để đảm bảo giống lúc bấm nút) hoặc mặc định
            p_fmt = st.session_state.get("checkout_print_fmt", "A5")
            
            st.info("Nếu hộp thoại in không tự bật, hãy bấm Ctrl+P trong khung hóa đơn.")
            # Render iframe invoice
            components.html(_render_bill_html(data, auto_print=True, print_format=p_fmt), height=600, scrolling=True)

    with c2:
        st.subheader("💡 Gợi ý")
        st.write("- Bạn có thể tải bill HTML để in lại bất cứ lúc nào.")
        st.write("- Sau khi trả phòng, trạng thái phòng sẽ chuyển sang **Chưa dọn**.")

    st.stop()

# --- 1. DANH SÁCH PHÒNG ĐANG Ở ---
occupied_rooms = get_occupied_rooms()

if not occupied_rooms:
    st.info("Hiện không có phòng nào đang có khách.")
    # Tiện ích: Hiển thị nút dọn phòng nhanh cho các phòng đang dơ
    st.write("---")
    st.caption("Tiện ích dọn phòng:")
    from src.db import get_all_rooms
    all_rooms = get_all_rooms()
    dirty_rooms = [r for r in all_rooms if r.get('status') == RoomStatus.DIRTY]
    if dirty_rooms:
        for dr in dirty_rooms:
            c1, c2 = st.columns([4, 1])
            c1.warning(f"Phòng {dr['id']} đang chờ dọn dẹp.")
            if c2.button("🧹 Đã dọn xong", key=f"clean_{dr['id']}"):
                update_room_status(dr['id'], RoomStatus.AVAILABLE)
                st.rerun()
    st.stop()

# --- 2. GIAO DIỆN CHECK-OUT ---
col_select, col_bill = st.columns([1, 2])

with col_select:
    st.subheader("Chọn phòng trả")
    # Tạo list ID phòng
    room_ids = [r['id'] for r in occupied_rooms]

    # Cho phép prefill phòng từ Dashboard (khi bấm Checkout ở Dashboard)
    prefill_room_id = st.session_state.pop("prefill_checkout_room_id", None)
    default_index = 0
    if prefill_room_id in room_ids:
        default_index = room_ids.index(prefill_room_id)

    selected_room_id = st.selectbox("Danh sách phòng đang ở", room_ids, index=default_index)
    
    # Lấy thông tin phòng & booking hiện tại
    selected_room = next((r for r in occupied_rooms if r['id'] == selected_room_id), None)
    booking_id = selected_room.get("current_booking_id")
    
    if booking_id:
        booking = get_booking_by_id(booking_id)
    else:
        st.error("Lỗi dữ liệu: Phòng đang ở nhưng không tìm thấy mã Booking!")
        st.stop()

    # Hiển thị tóm tắt khách
    with st.container(border=True):
        st.write(f"👤 **Khách:** {booking.get('customer_name')}")
        st.write(f"📞 **SĐT:** {booking.get('customer_phone')}")
        st.write(f"🕒 **Vào lúc:** {booking.get('check_in').strftime('%d/%m/%Y %H:%M')}")
        
        # Loại hình thuê (dùng try catch để tránh lỗi nếu data cũ chưa có field này)
        try:
            b_type = booking.get('booking_type', 'Theo giờ')
            # Nếu lưu dạng Enum trong DB thì nó là string, hiển thị trực tiếp
            st.write(f"🔖 **Hình thức:** {b_type}") 
        except:
            pass

with col_bill:
    st.subheader("🧾 Hóa đơn chi tiết")
    
    # Lấy cấu hình giá của loại phòng này để tính lại tiền (nếu cần)
    room_types = get_all_room_types()
    # Tìm pricing config
    r_type_code = selected_room.get('room_type_code')
    pricing = {}
    for rt in room_types:
        if rt['type_code'] == r_type_code:
            pricing = rt.get('pricing', {})
            break
            
    # --- TÍNH TOÁN THỜI GIAN THỰC TẾ ---
    check_in = booking.get('check_in')
    check_out_now = datetime.now()
    
    # Tính lại tiền phòng dựa trên giờ thực tế (Realtime calculation)
    # Lưu ý: Convert string booking_type sang Enum nếu cần, ở đây logic.py nhận string cũng được nếu xử lý khéo,
    # nhưng tốt nhất ta truyền đúng. Trong logic.py hiện tại đang so sánh Enum.
    
    # Mapping string sang Enum cho logic tính toán
    b_type_str = booking.get('booking_type')
    b_type_enum = BookingType.HOURLY
    if b_type_str == "Qua đêm": b_type_enum = BookingType.OVERNIGHT
    elif b_type_str == "Theo ngày": b_type_enum = BookingType.DAILY
    
    room_fee = calculate_estimated_price(check_in, check_out_now, b_type_enum, pricing)
    
    # --- TÍNH TIỀN DỊCH VỤ (New) ---
    calc_service_fee = calculate_service_total(booking_id)
    service_orders = get_orders_by_booking(booking_id)
    
    if service_orders:
        with st.expander(f"🛒 Chi tiết dịch vụ đã gọi ({calc_service_fee:,.0f} đ)", expanded=True):
            for o in service_orders:
                start_time = o.get("created_at")
                if isinstance(start_time, datetime):
                    t_str = start_time.strftime('%H:%M %d/%m')
                else:
                    t_str = ""
                st.caption(f"Order lúc {t_str}:")
                for item in o.get("items", []):
                    st.write(f"- {item['name']} x{item['qty']} = {item['total']:,.0f} đ")
            st.divider()
    
    # --- HÓA ĐƠN CHI TIẾT ---
    # Get current user role for permission check
    # Check permission for discount (Manager/Admin typically)
    can_discount = has_permission(Permission.MANAGE_ROOMS)
    
    # 1. Tiền phòng - hiển thị
    c1, c2 = st.columns([2, 1])
    c1.write("Tiền phòng (Tính đến hiện tại):")
    c2.write(f"**{int(room_fee):,} đ**")
    
    # 2. Dịch vụ
    c3, c4 = st.columns([2, 1])
    c3.write("Dịch vụ / Phụ thu:")
    c4.write(f"**{int(calc_service_fee):,} đ**")
    
    # 3. Giảm giá (Manager only)
    discount = 0.0
    if can_discount:
        discount = st.number_input(
            "Giảm giá (Chỉ Quản lý):", 
            value=0, 
            step=10000, 
            format="%d",
            key="discount_input"
        )
    
    # Calculate totals with discount
    subtotal = room_fee + calc_service_fee
    deposit = booking.get('deposit', 0.0)
    total_after_discount = subtotal - discount
    final_payment = total_after_discount - deposit
    
    st.divider()
    
    # Display calculation summary
    with st.container(border=True):
        st.markdown(f"**Tổng phụ:** {int(subtotal):,} đ")
        if discount > 0:
            st.markdown(f"**Giảm giá:** :red[-{int(discount):,} đ]")
        st.markdown(f"**Đã cọc:** -{int(deposit):,} đ")
        st.markdown(f"### 👉 KHÁCH CẦN TRẢ: :green[{int(final_payment):,} VNĐ]")
    
    st.write("")
    
    # Form chỉ chứa payment method và note
    with st.form("billing_form"):
        payment_method = st.radio("Phương thức thanh toán:", ["Tiền mặt", "Chuyển khoản", "Thẻ"], horizontal=True)
        note = st.text_area("Ghi chú hóa đơn (nếu có)")
        
        submitted = False
        if has_permission(Permission.CHECKIN_CHECKOUT):
             submitted = st.form_submit_button("💰 XÁC NHẬN THANH TOÁN & TRẢ PHÒNG", type="primary", use_container_width=True)
        else:
             st.error("⛔ Bạn không có quyền thực hiện thanh toán.")
        
        if submitted:
            # Use calculated values from outside form
            total_gross = total_after_discount
            
            success, msg = process_checkout(booking_id, selected_room_id, total_gross, payment_method, note, service_fee=float(calc_service_fee))
            if success:
                # Lưu dữ liệu hóa đơn để hiện màn hình bill
                st.session_state["checkout_success_data"] = {
                    "booking_id": booking_id,
                    "room_id": selected_room_id,
                    "customer_name": booking.get("customer_name", ""),
                    "customer_phone": booking.get("customer_phone", ""),
                    "check_in": check_in,
                    "check_out": check_out_now,
                    "room_fee": float(room_fee or 0.0),
                    "service_fee": float(calc_service_fee or 0.0),
                    "discount": float(discount or 0.0),
                    "total_gross": float(total_gross or 0.0),
                    "deposit": float(deposit or 0.0),
                    "final_payment": float(final_payment or 0.0),
                    "payment_method": payment_method,
                    "note": note,
                }
                st.session_state["checkout_print_now"] = False
                st.rerun()
            else:
                st.error(f"Lỗi: {msg}")




# --- 3. IN BILL (PREVIEW) ---
# Phần này hiển thị đơn giản dạng text để lễ tân copy hoặc xem lại
preview_total = subtotal - discount
preview_final = preview_total - deposit

discount_line = f"\n    Giảm giá:     -{discount:,.0f}" if discount > 0 else ""

with st.expander("Xem trước mẫu in bill"):
    st.code(f"""
    --- THE BAMBOO RESORT ---
    Hóa đơn thanh toán
    -------------------------
    Phòng: {selected_room_id}
    Khách: {booking.get('customer_name')}
    Check-in: {check_in.strftime('%d/%m/%Y %H:%M')}
    Check-out: {check_out_now.strftime('%d/%m/%Y %H:%M')}
    -------------------------
    Tiền phòng:   {room_fee:,.0f}
    Dịch vụ:      {calc_service_fee:,.0f}{discount_line}
    Tổng cộng:    {preview_total:,.0f}
    Đã cọc:       {deposit:,.0f}
    -------------------------
    THANH TOÁN:   {preview_final:,.0f} VNĐ
    -------------------------
    Cảm ơn quý khách!
    """, language="text")

