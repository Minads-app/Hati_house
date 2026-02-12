import streamlit as st
from datetime import datetime, timedelta
from src.db import get_all_rooms, get_all_room_types, create_booking, get_db, find_customer_by_phone, hold_room, release_room_hold # New
from src.models import Booking, BookingType, RoomStatus, BookingStatus, Permission
from src.logic import calculate_estimated_price
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, require_permission, has_permission

st.set_page_config(page_title="Đặt phòng", layout="wide")

require_login()
require_permission(Permission.VIEW_BOOKING)

apply_sidebar_style()
create_custom_sidebar_menu()

# --- INIT SESSION FOR HOLDING ---
if "user_session_id" not in st.session_state:
    import uuid
    st.session_state["user_session_id"] = str(uuid.uuid4())

# --- QUẢN LÝ STATE ---
# Biến này dùng để hiện màn hình "Thành công"
if "booking_success_data" not in st.session_state:
    st.session_state["booking_success_data"] = None

# Lấy cấu hình hệ thống (cho giá đặc biệt)
try:
    from src.db import get_system_config
    system_config = get_system_config("special_days")
except Exception as e:
    # st.error(f"Lỗi tải config: {e}") # Có thể uncomment để debug
    print(f"Error loading system config: {e}")
    system_config = {}

# Import hàm mới
from src.logic import get_applicable_price_config

# Hàm reset để quay lại màn hình đặt phòng
def reset_page():
    st.session_state["booking_success_data"] = None
    if "current_checkin_time" in st.session_state:
        st.session_state["current_checkin_time"] = datetime.now()
    st.rerun()

def check_customer_phone():
    """Callback khi nhập SĐT"""
    phone = st.session_state.get("c_phone", "")
    if phone and len(phone.strip()) >= 3:
        info = find_customer_by_phone(phone)
        if info:
             st.session_state["c_name"] = info["customer_name"]
             # Có thể fill thêm loại khách nếu muốn
             # if info.get("customer_type"):
             #    st.session_state["c_type"] = info["customer_type"]
             st.toast(f"Đã tìm thấy khách cũ: {info['customer_name']}", icon="👤")

# === MÀN HÌNH 1: KẾT QUẢ THÀNH CÔNG (HIỆN BILL) ===
if st.session_state["booking_success_data"]:
    data = st.session_state["booking_success_data"]
    
    st.balloons()
    st.title("✅ Đặt phòng thành công!")
    
    c1, c2 = st.columns([1, 1])
    with c1:
        st.success(f"Mã đặt phòng: {data['booking_id']}")
        # Hiển thị dạng vé/bill
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px dashed #ccc;">
            <h3 style="text-align: center; color: #0068c9;">PHIẾU XÁC NHẬN</h3>
            <p><b>Phòng:</b> {data['room_id']}</p>
            <p><b>Khách hàng:</b> {data['customer_name']} ({data['customer_phone']})</p>
            <hr>
            <p><b>Loại thuê:</b> {data['booking_type']}</p>
            <p><b>Check-in:</b> {data['check_in'].strftime('%d/%m/%Y %H:%M')}</p>
            <p><b>Check-out (Dự kiến):</b> {data['check_out'].strftime('%d/%m/%Y %H:%M')}</p>
            <hr>
            <p><b>Tổng tiền dự kiến:</b> {data['price']:,.0f} đ</p>
            <p><b>Đã cọc:</b> {data['deposit']:,.0f} đ</p>
            <p><b>Trạng thái:</b> {data['status_text']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        if st.button("⬅️ Quay lại trang đặt phòng", type="primary"):
            reset_page()

    with c2:
        st.info("💡 Hướng dẫn:")
        st.write("- Nếu khách đã nhận phòng: Phòng sẽ chuyển màu **ĐỎ** trên sơ đồ.")
        st.write("- Nếu chỉ đặt trước: Phòng sẽ chuyển màu **CAM** và chưa hiện trong danh sách trả phòng.")
    
    st.stop() # Dừng code tại đây, không hiện form bên dưới

# === MÀN HÌNH 2: FORM ĐẶT PHÒNG ===

st.title("🛎️ Check-in / Đặt phòng")

# Reset time logic
if "current_checkin_time" not in st.session_state:
    st.session_state["current_checkin_time"] = datetime.now()

try:
    # Lấy dữ liệu
    rooms = get_all_rooms()
    room_types = get_all_room_types()
    type_map = {t['type_code']: t for t in room_types}

    # Lọc phòng trống
    # Lọc phòng trống HOẶC phòng đang giữ bởi session này
    available_rooms = []
    current_session_id = st.session_state.get("user_session_id")
    
    for r in rooms:
        status = r.get('status')
        # Case 1: Available
        if status == RoomStatus.AVAILABLE or str(status) == "AVAILABLE" or status == "available":
            available_rooms.append(r)
        # Case 2: Held by ME
        elif status == RoomStatus.TEMP_LOCKED and r.get("locked_by") == current_session_id:
             available_rooms.append(r)

    available_room_ids = [r['id'] for r in available_rooms]

except Exception as e:
    st.error(f"Lỗi tải dữ liệu: {e}")
    st.stop()

# Callback cập nhật ngày trả khi đổi ngày nhận
def update_out_date():
    in_d = st.session_state.get("in_date")
    if in_d:
        st.session_state["out_date"] = in_d + timedelta(days=1)

if not available_rooms:
    st.warning("⚠️ Hết phòng trống!")
    if st.button("Tải lại"): st.rerun()
    st.stop()

    
# Grid Layout for Input Form
with st.container(border=True):
    # Chia thành 3 cột: Thông tin khách | Chọn phòng | Thanh toán
    col_customer, col_rooms, col_pay = st.columns([1.2, 1.2, 1], gap="medium")

    # --- CỘT 1: THÔNG TIN KHÁCH & THỜI GIAN ---
    with col_customer:
        st.caption("1. Thông tin khách")
        c_name = st.text_input("Họ tên khách (*)", key="c_name")
        c_phone = st.text_input("Số điện thoại (*)", key="c_phone", on_change=check_customer_phone)
        
        # Loại khách và hình thức thuê
        c_type = st.radio("Loại khách", ["Khách lẻ", "Khách đoàn"], horizontal=True, label_visibility="collapsed")
        
        # Logic hình thức thuê
        allowed_modes_all = set()
        for t in room_types:
             p = t.get('pricing', {})
             if p.get('enable_hourly', True): allowed_modes_all.add(BookingType.HOURLY)
             if p.get('enable_overnight', True): allowed_modes_all.add(BookingType.OVERNIGHT)
             if p.get('enable_daily', True): allowed_modes_all.add(BookingType.DAILY)
        
        mode_order = [BookingType.HOURLY, BookingType.OVERNIGHT, BookingType.DAILY]
        final_modes = [m for m in mode_order if m in allowed_modes_all]
        if not final_modes: final_modes = [BookingType.HOURLY]

        booking_mode = st.selectbox("Hình thức thuê", final_modes, format_func=lambda x: x.value)

        # Time Selection Logic
        frozen_now = st.session_state["current_checkin_time"]
        
        # Helper to generate slots
        def _generate_time_slots(selected_date):
             now = datetime.now()
             today = now.date()
             start_min = 0
             
             if selected_date == today:
                 minutes_from_midnight = now.hour * 60 + now.minute
                 remainder = minutes_from_midnight % 15
                 if remainder > 0:
                     minutes_from_midnight += (15 - remainder)
                 start_min = minutes_from_midnight
            
             slots = []
             for m in range(start_min, 24 * 60, 15):
                 from datetime import time as dtime
                 h = m // 60
                 min_ = m % 60
                 if h < 24:
                    slots.append(dtime(h, min_))
             return slots

        # Check-in time
        cc1, cc2 = st.columns(2, gap="small")
        with cc1:
            st.caption("Ngày nhận phòng")
            # Thêm callback update_out_date
            in_date = st.date_input("Ngày vào", value=frozen_now.date(), format="DD/MM/YYYY", label_visibility="collapsed", key="in_date", on_change=update_out_date)
            
            if booking_mode == BookingType.DAILY:
                 check_in_time = datetime.combine(in_date, datetime.strptime("14:00", "%H:%M").time())
                 st.info(f"🕒 {check_in_time.strftime('%H:%M')}")
            else:
                 slots = _generate_time_slots(in_date)
                 if not slots:
                     st.error("Hết giờ hôm nay!")
                     in_time_val = datetime.now().time()
                 else:
                     in_time_val = slots[0]
                     
                 in_time = st.selectbox("Giờ vào", slots, format_func=lambda t: t.strftime("%H:%M"), label_visibility="collapsed")
                 check_in_time = datetime.combine(in_date, in_time)

        with cc2:
            st.caption("Ngày trả phòng")
            if booking_mode == BookingType.HOURLY:
                default_out = check_in_time + timedelta(hours=2)
            elif booking_mode == BookingType.OVERNIGHT:
                tomorrow = check_in_time + timedelta(days=1)
                default_out = tomorrow.replace(hour=12, minute=0, second=0)
            else: 
                tomorrow = check_in_time + timedelta(days=1)
                default_out = tomorrow.replace(hour=12, minute=0, second=0)
            
            if booking_mode == BookingType.DAILY:
                # Nếu chưa có trong session, set default
                if "out_date" not in st.session_state:
                    st.session_state["out_date"] = default_out.date()
                
                # Dùng key="out_date" để bind với session_state
                out_date = st.date_input("Ngày ra", format="DD/MM/YYYY", label_visibility="collapsed", key="out_date")
                check_out_time = datetime.combine(out_date, datetime.strptime("12:00", "%H:%M").time())
                st.info(f"🕒 {check_out_time.strftime('%H:%M')}")
            else:
                out_date = st.date_input("Ngày ra", value=default_out.date(), format="DD/MM/YYYY", label_visibility="collapsed", key="out_date")
                out_time = st.time_input("Giờ ra", value=default_out.time(), step=900, label_visibility="collapsed", key="out_time")
                check_out_time = datetime.combine(out_date, out_time)

    # --- CỘT 2: CHỌN PHÒNG ---
    with col_rooms:
        st.caption("2. Chọn phòng")
        prefill_room_id = st.session_state.pop("prefill_room_id", None)

        # Filter rooms based on booking mode
        compatible_room_ids = []
        for r in available_rooms:
            t = type_map.get(r['room_type_code'], {})
            p = t.get('pricing', {})
            
            is_compat = False
            if booking_mode == BookingType.HOURLY and p.get('enable_hourly', True): is_compat = True
            elif booking_mode == BookingType.OVERNIGHT and p.get('enable_overnight', True): is_compat = True
            elif booking_mode == BookingType.DAILY and p.get('enable_daily', True): is_compat = True
            
            if is_compat:
                compatible_room_ids.append(r['id'])
        
        # Logic chọn phòng & Giữ chỗ (Hold) - WORKFLOW MỚI
        
        # 1. Hàm xử lý khi bấm nút "Thoát" hoặc "Huỷ chọn"
        def release_all_held_rooms():
            current_held = st.session_state.get("last_admin_held_rooms", [])
            for rid in current_held:
                release_room_hold(rid, st.session_state["user_session_id"])
            st.session_state["last_admin_held_rooms"] = []
            st.session_state["admin_selected_rooms"] = [] # Reset multiselect
            st.session_state["admin_single_room"] = None # Reset single select
            st.toast("Đã huỷ chọn và nhả phòng", icon="🔓")

        # 2. UI chọn phòng
        selected_rooms = []
        is_held = False # Trạng thái đã giữ chỗ thành công chưa
        current_held = st.session_state.get("last_admin_held_rooms", [])

        if c_type == "Khách đoàn":
            # Nếu đang giữ phòng, không cho chọn lại (phải huỷ trước)
            if current_held:
                st.info(f"🔒 Đang giữ {len(current_held)} phòng: {', '.join(current_held)}")
                selected_rooms = current_held
                is_held = True
            else:
                 selected_rooms = st.multiselect(
                    "Chọn phòng", 
                    compatible_room_ids, 
                    default=[], 
                    label_visibility="collapsed", 
                    placeholder="Mời chọn phòng...",
                    key="admin_selected_rooms"
                )
        else:
             if current_held:
                st.info(f"🔒 Đang giữ phòng: {current_held[0]}")
                selected_rooms = current_held
                is_held = True
             else:
                s_r = st.selectbox(
                    "Chọn phòng", 
                    [""] + compatible_room_ids, # Thêm option rỗng
                    index=0, 
                    label_visibility="collapsed",
                    key="admin_single_room",
                    format_func=lambda x: "Mời chọn phòng..." if x == "" else x
                )
                if s_r: selected_rooms = [s_r]

        if not selected_rooms:
             st.info("⬅️ Vui lòng chọn phòng để bắt đầu.")
             st.stop()

        # 3. Nút xác nhận giữ / huỷ
        if not is_held:
            st.warning(f"Bạn chọn: {', '.join(selected_rooms)}. Bấm xác nhận để giữ phòng.")
            if st.button("🔒 Xác nhận giữ phòng (5 phút)", type="primary"):
                 # Thực hiện Hold
                valid_holds = []
                for rid in selected_rooms:
                    success, msg = hold_room(rid, st.session_state["user_session_id"], duration_minutes=5)
                    if success:
                        valid_holds.append(rid)
                    else:
                        st.error(f"Phòng {rid}: {msg}")
                
                if valid_holds:
                    st.session_state["last_admin_held_rooms"] = valid_holds
                    st.rerun() # Reload để update UI sang trạng thái "Đang giữ"
        else:
            # Đang giữ -> Cho phép Huỷ/Thoát
            if st.button("❌ Huỷ chọn & Thoát", type="secondary"):
                release_all_held_rooms()
                st.rerun()

        # Hiển thị thông tin phòng
        if selected_rooms and len(selected_rooms) == 1:
            rid = selected_rooms[0]
            r_obj = next((r for r in available_rooms if r['id'] == rid), None)
            if r_obj:
                t_info = type_map.get(r_obj['room_type_code'], {})
                p_info = t_info.get('pricing', {})
                
                price_html = ""
                if booking_mode == BookingType.OVERNIGHT:
                     price_html = f'<div style="display: flex; justify-content: space-between;"><span>Qua đêm:</span> <b>{p_info.get("overnight_price", 0):,.0f}</b></div>'
                elif booking_mode == BookingType.DAILY:
                     price_html = f'<div style="display: flex; justify-content: space-between;"><span>Theo ngày:</span> <b>{p_info.get("daily_price", 0):,.0f}</b></div>'
                elif booking_mode == BookingType.HOURLY:
                     h_price = p_info.get('hourly_blocks', {}).get('1', 0)
                     price_html = f'<div style="display: flex; justify-content: space-between;"><span>Theo giờ (1h):</span> <b>{h_price:,.0f}</b></div>'

                st.markdown(f"""
                <div class="room-info-card">
                    <div class="room-info-header">ℹ️ {t_info.get('name', 'Phòng')} ({rid})</div>
                    <div class="room-info-price">
                        {price_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    if not selected_rooms:
        st.info("⬅️ Vui lòng chọn phòng.")
        st.stop()
    
    with col_pay:
        st.caption("3. Xác nhận & Thanh toán")
        
        # Logic tính tiền (Tổng các phòng)
        total_est_price = 0
        details_text = []

        for rid in selected_rooms:
            ro = next((r for r in available_rooms if r['id'] == rid), None)
            if ro:
                ti = type_map.get(ro['room_type_code'], {})
                price_cfg = get_applicable_price_config(check_in_time.date(), ti, system_config)
                p = calculate_estimated_price(check_in_time, check_out_time, booking_mode, price_cfg)
                total_est_price += p
                details_text.append(f"- {rid}: {p:,.0f} đ")
        
        # Show breakdown if multiple
        if len(selected_rooms) > 1:
             with st.expander(f"Chi tiết {len(selected_rooms)} phòng"):
                 for l in details_text: st.write(l)

        # Debug info (optional)
        if selected_rooms:
            first_ro = next((r for r in available_rooms if r['id'] == selected_rooms[0]), None)
            if first_ro:
                first_ti = type_map.get(first_ro['room_type_code'], {})
                first_pricing = get_applicable_price_config(check_in_time.date(), first_ti, system_config)
                if first_pricing != first_ti.get('pricing', {}):
                     st.caption("ℹ️ Đang áp dụng giá đặc biệt")

        st.metric("Tổng tạm tính", f"{total_est_price:,.0f} đ")
        deposit = st.number_input("Tiền cọc", step=50000, format="%d")

        # st.write("")
        is_checkin_now = st.checkbox("Check-in ngay?", value=True)
        btn_label = "✅ CHECK-IN" if is_checkin_now else "💾 LƯU"
        
        if has_permission(Permission.CREATE_BOOKING):
            if st.button(btn_label, type="primary", use_container_width=True):
                if not c_name:
                    st.error("Thiếu tên khách!")
                elif not c_phone:
                    st.error("Thiếu số điện thoại!")
                elif check_out_time <= check_in_time:
                    st.error("Giờ ra sai!")
                else:
                    success_count = 0
                    created_ids = []
                    
                    # Avg deposit
                    avg_deposit = deposit / len(selected_rooms) if selected_rooms and deposit else 0

                    for rid in selected_rooms:
                        # Recalculate price
                        ro = next((r for r in available_rooms if r['id'] == rid), None)
                        if ro:
                            ti = type_map.get(ro['room_type_code'], {})
                            price_cfg = get_applicable_price_config(check_in_time.date(), ti, system_config)
                            p_room = calculate_estimated_price(check_in_time, check_out_time, booking_mode, price_cfg)
                            
                            new_bk = Booking(
                                room_id=rid,
                                customer_name=c_name,
                                customer_phone=c_phone,
                                customer_type=c_type,
                                booking_type=booking_mode,
                                check_in=check_in_time,
                                check_out_expected=check_out_time,
                                price_original=p_room,
                                deposit=avg_deposit,
                                status=BookingStatus.CHECKED_IN if is_checkin_now else BookingStatus.CONFIRMED,
                                source="direct"
                            )
                            suc, rez_id = create_booking(new_bk.to_dict())
                            if suc:
                                success_count += 1
                                created_ids.append(rez_id)
                    
                    if success_count == len(selected_rooms):
                         st.success(f"Đã tạo {success_count} booking thành công!")
                         # Clear state
                         st.session_state["selected_rooms"] = []
                         st.rerun()
                    else:
                        st.error(f"Có lỗi xảy ra! Chỉ tạo được {success_count}/{len(selected_rooms)} phòng.")