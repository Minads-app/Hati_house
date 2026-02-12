import base64
from datetime import datetime, timedelta, date, time as dtime
import os
import sys
from urllib.parse import quote_plus

import streamlit as st

# Đảm bảo có thể import được package src khi chạy file lẻ
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.config import AppConfig # Import Config
from src.db import (
    get_all_rooms,
    get_all_room_types,
    create_booking,
    update_online_payment_proof,
    update_online_payment_proof,
    get_payment_config,
    get_booking_by_id,
    get_system_config,
    hold_room,         # New
    release_room_hold, # New
    get_resort_name,
)
from src.models import Booking, BookingType, RoomStatus
from src.ui import apply_sidebar_style, create_custom_sidebar_menu
from src.logic import calculate_estimated_price, get_applicable_price_config # Import hàm logic mới

st.set_page_config(page_title="Đặt phòng Online", layout="wide")
apply_sidebar_style()
#create_custom_sidebar_menu()

# --- INIT SESSION FOR HOLDING ---
if "user_session_id" not in st.session_state:
    import uuid
    st.session_state["user_session_id"] = str(uuid.uuid4())

st.title(f"🌐 Đặt phòng Online - {get_resort_name()}")
st.caption(
    "Khách tự đặt phòng, chuyển khoản và gửi hình chụp thanh toán. Lễ tân sẽ kiểm tra và xác nhận đặt cọc."
)

# --- STEP 1: FORM ĐẶT PHÒNG ---
st.markdown("### 1️⃣ Thông tin đặt phòng")

rooms = get_all_rooms()
room_types = get_all_room_types()
# Lấy cấu hình hệ thống
try:
    system_config = get_system_config("special_days")
except:
    system_config = {}

type_map = {t["type_code"]: t for t in room_types}

# Filter available rooms AND rooms held by THIS session
session_id = st.session_state["user_session_id"]
available_rooms = []
for r in rooms:
    status = r.get("status")
    # Phòng OK nếu AVAILABLE
    if status == RoomStatus.AVAILABLE:
        available_rooms.append(r)
    # HOẶC nếu đang TEMP_LOCKED bởi chính mình
    elif status == RoomStatus.TEMP_LOCKED and r.get("locked_by") == session_id:
        available_rooms.append(r)

available_room_ids = [r["id"] for r in available_rooms]

if not available_rooms:
    st.warning("Hiện tại chưa có phòng trống để đặt online. Vui lòng liên hệ lễ tân.")
    st.stop()

col_info, col_room, col_time = st.columns([1.2, 1, 1.2])

with col_info:
    c_name = st.text_input("Họ tên khách (*)")
    c_phone = st.text_input("Số điện thoại liên hệ (*)")
    c_note = st.text_area("Ghi chú (nếu có)")

with col_room:
    # Chọn loại phòng trước cho dễ nhìn
    st.markdown("**Loại phòng mong muốn**")
    type_options = {
        t["type_code"]: f"{t['name']} ({t['type_code']})" for t in room_types
    }
    selected_type_code = st.selectbox(
        "Loại phòng",
        options=list(type_options.keys()),
        format_func=lambda x: type_options[x],
    )

    # Lọc phòng trống theo loại đã chọn
    filtered_rooms = [
        r for r in available_rooms if r["room_type_code"] == selected_type_code
    ]
    filtered_room_ids = [r["id"] for r in filtered_rooms]

    if not filtered_rooms:
        st.warning("Loại phòng này hiện đã hết. Vui lòng chọn loại khác.")

    # Logic chọn phòng & Giữ chỗ (Hold)
    def on_room_change():
        # Release old room if exists
        old_room = st.session_state.get("last_held_room")
        if old_room:
             release_room_hold(old_room, session_id)
        
        # Hold new room
        new_room = st.session_state.get("selected_room_id_key")
        if new_room:
             success, msg = hold_room(new_room, session_id, duration_minutes=5)
             if success:
                 st.session_state["last_held_room"] = new_room
                 st.toast(f"Đang giữ phòng {new_room} trong 5 phút", icon="⏳")
             else:
                 st.error(f"Không thể giữ phòng: {msg}")
                 # Force reload to update list
                 
    selected_room_id = st.selectbox(
        "Chọn phòng (nếu muốn chọn cụ thể)",
        options=filtered_room_ids or available_room_ids,
        key="selected_room_id_key",
        on_change=on_room_change
    )
    
    # Trigger hold on first load / default selection
    if selected_room_id and st.session_state.get("last_held_room") != selected_room_id:
         # Initial hold for default selection
         success, msg = hold_room(selected_room_id, session_id, duration_minutes=5)
         if success:
             st.session_state["last_held_room"] = selected_room_id
         else:
             # Should warn user but it's tricky inside render loop
             pass

def _generate_time_slots(selected_date: date) -> list[dtime]:
    """Sinh danh sách mốc giờ theo bước 15 phút.

    - Nếu ngày chọn là hôm nay: chỉ cho phép từ thời điểm hiện tại trở đi (làm tròn lên 15 phút).
    - Nếu ngày > hôm nay: cho phép từ 00:00 đến 23:45.
    """
    now = datetime.now()
    today = now.date()

    if selected_date <= today:
        # Làm tròn lên mốc 15 phút tiếp theo
        minutes_from_midnight = now.hour * 60 + now.minute
        next_slot_min = ((minutes_from_midnight + 14) // 15) * 15
        # Nếu đã qua 23:45 thì coi như hết khung giờ
        if next_slot_min > 23 * 60 + 45:
            return []
        start_min = next_slot_min
    else:
        start_min = 0

    slots: list[dtime] = []
    for m in range(start_min, 24 * 60, 15):
        h = m // 60
        minute = m % 60
        slots.append(dtime(hour=h, minute=minute))
    return slots

with col_time:
    st.markdown("**Thời gian lưu trú**")
    
    # Lọc hình thức thuê
    pricing_data = type_map.get(selected_type_code, {}).get("pricing", {})
    allowed_modes = []
    if pricing_data.get('enable_hourly', True): allowed_modes.append(BookingType.HOURLY)
    if pricing_data.get('enable_overnight', True): allowed_modes.append(BookingType.OVERNIGHT)
    if pricing_data.get('enable_daily', True): allowed_modes.append(BookingType.DAILY)
    
    if not allowed_modes:
        st.error("Loại phòng này hiện không cho phép đặt Online.")
        st.stop()
        
    booking_mode = st.selectbox(
        "Hình thức thuê",
        allowed_modes,
        format_func=lambda x: x.value,
    )

    now = datetime.now()
    in_date = st.date_input("Ngày đến", value=now.date(), format="DD/MM/YYYY")

    if booking_mode == BookingType.DAILY:
        # KHÓA CỨNG: 14:00
        in_time = dtime(14, 0)
        check_in_time = datetime.combine(in_date, in_time)
        st.info("🕒 Vui lòng check-in lúc 14:00")
    else:
        # Logic cũ cho Hourly/Overnight
        # Sinh danh sách mốc giờ hợp lệ theo ngày, bước 15 phút
        time_slots = _generate_time_slots(in_date)
        if not time_slots:
            st.error("Hôm nay đã hết khung giờ đặt phòng online. Vui lòng chọn ngày khác.")
            st.stop()
        
        in_time = st.selectbox(
            "Giờ đến (bước 15 phút)",
            options=time_slots,
            format_func=lambda t: t.strftime("%H:%M"),
        )
        check_in_time = datetime.combine(in_date, in_time)

    # Gợi ý giờ trả dựa trên check_in_time
    if booking_mode == BookingType.HOURLY:
        default_out = check_in_time + timedelta(hours=2)
    elif booking_mode == BookingType.OVERNIGHT:
        tomorrow = check_in_time + timedelta(days=1)
        default_out = tomorrow.replace(hour=12, minute=0, second=0)
    else:
        # DAILY: Trả 12:00 hôm sau
        tomorrow = check_in_time + timedelta(days=1)
        default_out = tomorrow.replace(hour=12, minute=0, second=0)

    # Widget chọn Ngày/Giờ trả
    if booking_mode == BookingType.DAILY:
        # KHÓA CỨNG: 12:00
        out_date = st.date_input("Ngày trả dự kiến", value=default_out.date(), format="DD/MM/YYYY")
        out_time = dtime(12, 0)
        check_out_time = datetime.combine(out_date, out_time)
        st.info("🕒 Vui lòng check-out lúc 12:00")
    else:
        out_date = st.date_input(
            "Ngày trả dự kiến", value=default_out.date(), format="DD/MM/YYYY"
        )
        out_time = st.time_input(
            "Giờ trả dự kiến", value=default_out.time(), step=900
        )
        check_out_time = datetime.combine(out_date, out_time)

# --- TÍNH TIỀN DỰ KIẾN & CHỌN HÌNH THỨC THANH TOÁN ---
st.markdown("### 2️⃣ Thanh toán")

# Logic chọn giá (Regular / Weekend / Holiday)
t_info = type_map.get(selected_type_code, {})
effective_pricing = get_applicable_price_config(check_in_time.date(), t_info, system_config)

estimated_price = calculate_estimated_price(
    check_in_time, check_out_time, booking_mode, effective_pricing
)

# Debug info
if effective_pricing != t_info.get('pricing', {}):
    st.info("💡 Đang áp dụng giá đặc biệt (Lễ/Tết hoặc Cuối tuần)")

col_pay_left, col_pay_right = st.columns([1, 1])

with col_pay_left:
    st.metric("Tổng tiền dự kiến", f"{estimated_price:,.0f} đ")

with col_pay_right:
    pay_option = st.radio(
        "Hình thức thanh toán",
        [
            "Thanh toán toàn bộ (100%)",
            "Đặt cọc trước (50%)",
        ],
    )

    if pay_option == "Thanh toán toàn bộ (100%)":
        deposit = estimated_price
        st.info(
            f"Khách sẽ chuyển khoản toàn bộ số tiền: **{deposit:,.0f} đ** để giữ phòng."
        )
        online_payment_type = "full"
    else:
        # Bắt buộc 50%
        deposit = int(estimated_price * 0.5)
        st.info(f"Số tiền đặt cọc bắt buộc (50%): **{deposit:,.0f} đ**")
        online_payment_type = "deposit"

st.markdown("---")

if "online_booking_id" not in st.session_state:
    st.session_state["online_booking_id"] = None
if "online_payment_uploaded" not in st.session_state:
    st.session_state["online_payment_uploaded"] = False

btn_book = st.button(
    "✅ Gửi yêu cầu đặt phòng & xem mã QR thanh toán",
    type="primary",
    use_container_width=True,
)

if btn_book:
    if not c_name or not c_phone:
        st.error("Vui lòng nhập đầy đủ Họ tên và Số điện thoại.")
    elif check_out_time <= check_in_time:
        st.error("Giờ trả phải lớn hơn Giờ đến.")
    else:
        new_bk = Booking(
            room_id=selected_room_id,
            customer_name=c_name,
            customer_phone=c_phone,
            customer_type="Khách online",
            booking_type=booking_mode,
            check_in=check_in_time,
            check_out_expected=check_out_time,
            price_original=estimated_price,
            deposit=float(deposit),
            note=c_note,
            is_online=True,
            online_payment_type=online_payment_type,
            online_payment_status="pending",
        )

        ok, result = create_booking(new_bk, is_checkin_now=False)
        if ok:
            st.success(
                "Đã tạo yêu cầu đặt phòng! Vui lòng quét mã QR bên dưới và tải lên hình chụp thanh toán."
            )
            st.session_state["online_booking_id"] = result
        else:
            st.error(f"Lỗi hệ thống khi tạo booking: {result}")

# --- STEP 3: HIỂN THỊ QR & UPLOAD ẢNH THANH TOÁN ---
booking_id = st.session_state.get("online_booking_id")

if booking_id:
    st.markdown("### 3️⃣ Thanh toán & gửi hình chụp")

    col_qr, col_upload = st.columns([1, 1])

    with col_qr:
        st.markdown("**Quét mã QR thanh toán**")

        cfg = get_payment_config()
        bank_id = cfg.get("bank_id")
        acc_no = cfg.get("account_number")
        if bank_id and acc_no:
            # Số tiền cần thanh toán = tiền đặt cọc (VND), ép về int để truyền cho VietQR
            amount_vnd = int(float(deposit or 0))
            qr_url = (
                f"https://img.vietqr.io/image/"
                f"{bank_id}-{acc_no}-compact2.png?"
                f"accountName={quote_plus(cfg.get('account_name',''))}&"
                f"addInfo={quote_plus(cfg.get('note','Thanh toan tien phong'))}&"
                f"amount={amount_vnd}"
            )
            st.image(qr_url, caption="VietQR ngân hàng", use_column_width=True)
            if cfg.get("bank_name") or cfg.get("account_number"):
                st.caption(
                    f"{cfg.get('bank_name','')} - STK: {cfg.get('account_number','')} ({cfg.get('account_name','')})"
                )
        else:
            st.warning(
                "Chưa khai báo đủ Mã ngân hàng (VietQR bankId/BIN) và Số tài khoản. Vui lòng vào trang 'Cài đặt > Hệ thống & Thanh toán' để cấu hình."
            )

    with col_upload:
        st.markdown("**Tải hình chụp màn hình chuyển khoản**")
        uploaded = st.file_uploader(
            "Chọn file ảnh (PNG/JPG/JPEG)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=False,
        )

        if uploaded is not None:
            img_bytes = uploaded.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            if st.button(
                "📤 Gửi hình chụp thanh toán cho lễ tân",
                type="primary",
                use_container_width=True,
            ):
                try:
                    update_online_payment_proof(
                        booking_id,
                        img_b64,
                        uploaded.name,
                        uploaded.type,
                    )
                    st.success(
                        "Đã gửi hình chụp thanh toán. Lễ tân sẽ kiểm tra và xác nhận đặt cọc trong thời gian sớm nhất."
                    )
                    st.session_state["online_payment_uploaded"] = True
                except Exception as e:
                    st.error(f"Lỗi khi lưu hình chụp thanh toán: {e}")

    # Sau khi upload thành công => hiển thị Phiếu xác nhận đặt phòng Online
    if st.session_state.get("online_payment_uploaded"):
        st.markdown("---")
        st.markdown("### 4️⃣ Phiếu xác nhận đặt phòng (Chờ lễ tân xác nhận)")

        try:
            bk = get_booking_by_id(booking_id) or {}
        except Exception:
            bk = {}

        st.success(f"Mã đặt phòng (Bill ID): **{booking_id}**")
        st.markdown(
            f"""
            **Phòng:** {bk.get('room_id', selected_room_id)}  
            **Khách:** {bk.get('customer_name', c_name)} ({bk.get('customer_phone', c_phone)})  
            **Check-in dự kiến:** {bk.get('check_in').strftime('%d/%m/%Y %H:%M') if bk.get('check_in') else check_in_time.strftime('%d/%m/%Y %H:%M')}  
            **Check-out dự kiến:** {bk.get('check_out_expected').strftime('%d/%m/%Y %H:%M') if bk.get('check_out_expected') else check_out_time.strftime('%d/%m/%Y %H:%M')}  
            **Số tiền đã chuyển / đặt cọc:** {float(bk.get('deposit', deposit) or 0):,.0f} đ  

            **Trạng thái:** Chờ lễ tân kiểm tra và xác nhận.
            """
        )
