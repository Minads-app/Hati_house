import streamlit as st
from src.db import (
    get_all_rooms,
    get_all_room_types,
    check_in_reserved_room,
    get_booking_by_id,
    get_pending_online_bookings,
    get_confirmed_online_bookings,
    confirm_online_booking,
    get_active_bookings_dict,
    get_system_update_counter,
    get_resort_name,
)
from src.models import RoomStatus, Permission
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, require_permission

st.set_page_config(page_title="Sơ đồ phòng", layout="wide")

require_login()
require_permission(Permission.VIEW_DASHBOARD)

apply_sidebar_style()
create_custom_sidebar_menu()

st.title(f"🏨 Sơ đồ phòng - {get_resort_name()}")

# --- SMART POLLING (Counter-based) --- TẠM TẮT ---
# # Init session state
# if "sp_counter" not in st.session_state:
#     st.session_state["sp_counter"] = -1  # Force first fetch
# if "sp_rooms" not in st.session_state:
#     st.session_state["sp_rooms"] = None
# if "sp_bookings" not in st.session_state:
#     st.session_state["sp_bookings"] = None
#
# st.sidebar.markdown("### ⏱ Cài đặt")
# enable_polling = st.sidebar.toggle("Tự động cập nhật (Real-time)", value=True, help="Tự động kiểm tra thay đổi mỗi 5 giây. Chi phí: ~1 read/5s (rất rẻ).")
#
# if enable_polling:
#     try:
#         from streamlit_autorefresh import st_autorefresh
#         st_autorefresh(interval=5000, key="dashboard_autorefresh")
#     except ImportError:
#         st.sidebar.error("⚠️ Cần cài: pip install streamlit-autorefresh")
#
# # Force Reload Button
# if st.sidebar.button("🔄 Tải lại ngay", width='stretch'):
#     st.session_state["sp_counter"] = -1  # Force re-fetch
#     st.rerun()
#
# # --- CHECK COUNTER (1 read) ---
# server_counter = get_system_update_counter()
# local_counter = st.session_state["sp_counter"]
#
# if server_counter != local_counter or st.session_state["sp_rooms"] is None:
#     rooms = get_all_rooms()
#     active_bookings_map = get_active_bookings_dict()
#     st.session_state["sp_rooms"] = rooms
#     st.session_state["sp_bookings"] = active_bookings_map
#     st.session_state["sp_counter"] = server_counter
# else:
#     rooms = st.session_state["sp_rooms"]
#     active_bookings_map = st.session_state["sp_bookings"]
# --- END TẠM TẮT ---

# Luôn fetch dữ liệu mới khi tải trang
rooms = get_all_rooms()
active_bookings_map = get_active_bookings_dict()

types = get_all_room_types()
type_map = {t["type_code"]: t["name"] for t in types}

# --- 1b. BOOKING ONLINE CHỜ XÁC NHẬN & LỊCH SỬ ---
col_pending, col_history = st.columns(2)

with col_pending:
    pending_online = get_pending_online_bookings()
    if pending_online:
        with st.expander(
            f"📨 {len(pending_online)} booking online đang CHỜ xác nhận thanh toán",
            expanded=True,
        ):
            for b in pending_online:
                room_id = b.get("room_id", "")
                booking_id = b.get("id", "")

                st.markdown(
                    f"**Phòng {room_id}** - {b.get('customer_name','')} ({b.get('customer_phone','')})"
                )

                pay_type = b.get("online_payment_type", "")
                status_raw = b.get("online_payment_status", "pending")
                status_label = (
                    "Chưa upload chứng từ"
                    if status_raw == "pending"
                    else "Chờ lễ tân xác nhận"
                )

                st.caption(
                    f"Hình thức: {pay_type} | Trạng thái thanh toán: **{status_label}**"
                )
                check_in = b.get("check_in")
                check_out = b.get("check_out_expected")
                if check_in:
                    st.write(f"- Check-in: {check_in.strftime('%d/%m/%Y %H:%M')}")
                if check_out:
                    st.write(f"- Check-out dự kiến: {check_out.strftime('%d/%m/%Y %H:%M')}")

                # Hiển thị thumbnail hình chụp thanh toán (nếu có)
                img_b64 = b.get("payment_screenshot_b64")
                if img_b64:
                    import base64

                    st.write("Hình chụp thanh toán (thu nhỏ):")
                    st.image(
                        base64.b64decode(img_b64),
                        caption=b.get("payment_screenshot_name", ""),
                        width=260,
                    )
                    with st.expander("🔍 Xem ảnh kích thước lớn"):
                        st.image(
                            base64.b64decode(img_b64),
                            caption=b.get("payment_screenshot_name", ""),
                            width='stretch',
                        )

                # Nút xác nhận đã nhận tiền
                if status_raw != "confirmed" and booking_id:
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        # Check permission for update
                        from src.ui import has_permission
                        if has_permission(Permission.UPDATE_BOOKING):
                            clicked = st.button(
                                "✅ Xác nhận đã nhận tiền",
                                key=f"confirm_online_{booking_id}",
                                width='stretch',
                            )
                            if clicked:
                                ok, msg = confirm_online_booking(booking_id)
                                if ok:
                                    st.success(
                                        "Đã xác nhận đã nhận tiền. Booking đã được cập nhật."
                                    )
                                    st.rerun()
                                else:
                                    st.error(f"Lỗi khi xác nhận: {msg}")
                        else:
                             st.caption("🔒 Cần quyền sửa booking")
                    with c2:
                        st.caption(
                            "Sau khi xác nhận, booking sẽ không còn trong danh sách chờ."
                        )

                st.markdown("---")

with col_history:
    confirmed_online = get_confirmed_online_bookings(limit=20)
    with st.expander(
        f"📁 Lịch sử booking online đã xác nhận ({len(confirmed_online)} gần nhất)",
        expanded=False,
    ):
        if not confirmed_online:
            st.caption("Chưa có booking online nào được xác nhận.")
        else:
            for b in confirmed_online:
                room_id = b.get("room_id", "")
                st.markdown(
                    f"**Phòng {room_id}** - {b.get('customer_name','')} ({b.get('customer_phone','')})"
                )
                check_in = b.get("check_in")
                if check_in:
                    st.caption(
                        f"Check-in dự kiến: {check_in.strftime('%d/%m/%Y %H:%M')}"
                    )

                img_b64 = b.get("payment_screenshot_b64")
                if img_b64:
                    import base64

                    st.image(
                        base64.b64decode(img_b64),
                        caption="Ảnh thanh toán (thu nhỏ)",
                        width=220,
                    )
                    with st.expander("🔍 Xem ảnh chi tiết", expanded=False):
                        st.image(
                            base64.b64decode(img_b64),
                            caption=b.get("payment_screenshot_name", ""),
                            width='stretch',
                        )

                st.markdown("---")

# Hàm helper để lấy màu sắc và icon dựa trên trạng thái
def get_status_style(status_str):
    # Map string status sang màu sắc, icon và text hiển thị
    if status_str == RoomStatus.AVAILABLE:
        return "🟢", "#e6fffa", "border: 2px solid #4caf50;", "Trống" # Xanh lá
    elif status_str == RoomStatus.RESERVED:
        return "🟠", "#fff3e0", "border: 2px solid #ff9800;", "Đặt trước" # Cam (Đặt trước)
    elif status_str == RoomStatus.PENDING_PAYMENT:
        return "💸", "#e0e7ff", "border: 2px solid #3b82f6;", "Chờ TT" # Xanh dương (Chờ thanh toán)
    elif status_str == RoomStatus.OCCUPIED:
        return "🔴", "#FF7DB0", "border: 2px solid #f44336;", "Đang ở" # Đỏ (Đang ở)
    elif status_str == RoomStatus.DIRTY:
        return "🧹", "#fffbe6", "border: 2px solid #ffeb3b;", "Cần dọn" # Vàng (Dơ)
    elif status_str == RoomStatus.MAINTENANCE:
        return "🔧", "#f0f2f6", "border: 2px solid #9e9e9e;", "Bảo trì" # Xám (Bảo trì)
    elif status_str == RoomStatus.TEMP_LOCKED:
        return "⏳", "#fe84d8", "border: 2px solid #ff0000;", "Đang thao tác" # Vàng cam
    else:
        return "❓", "#ffffff", "border: 2px solid #ccc;", "Khác"

# --- 2. THANH CÔNG CỤ (FILTER, SEARCH & STATS) ---
col_filter, col_stats = st.columns([1.2, 2.8])

with col_filter:
    # Lấy danh sách khu vực duy nhất
    floors = sorted(list(set([str(r["floor"]) for r in rooms]))) if rooms else []
    filter_floor = st.multiselect("Lọc theo Khu vực", options=floors)

    st.markdown("**🔍 Tìm khách ĐẶT TRƯỚC**")
    search_text = st.text_input(
        "Nhập tên khách hoặc SĐT",
        placeholder="VD: An, 09...",
        key="search_reserved_guest",
    )

# Tính toán thống kê
total = len(rooms)
count_available = len([r for r in rooms if r.get("status") == RoomStatus.AVAILABLE])
count_occupied = len([r for r in rooms if r.get("status") == RoomStatus.OCCUPIED])
count_reserved = len([r for r in rooms if r.get("status") == RoomStatus.RESERVED])
count_dirty = len([r for r in rooms if r.get("status") == RoomStatus.DIRTY])

with col_stats:
    # Hiển thị metrics dạng ngang
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng phòng", total)
    c2.metric("Trống", count_available)
    c3.metric("Đang ở", count_occupied, delta_color="inverse")  # Màu đỏ
    c4.metric("Đặt trước", count_reserved)  # Màu cam
    c5.metric("Cần dọn", count_dirty)  # Màu vàng

    # Nếu có nhập search -> hiển thị kết quả nhanh
    if search_text.strip():
        q = search_text.strip().lower()
        reserved_rooms = [r for r in rooms if r.get("status") == RoomStatus.RESERVED]
        matched = []
        for r in reserved_rooms:
            bk_id = r.get("current_booking_id")
            if not bk_id:
                continue
            # Use cached map instead of DB call
            bk = active_bookings_map.get(bk_id) or {}
            
            name = (bk.get("customer_name") or "").lower()
            phone = (bk.get("customer_phone") or "").lower()
            if q in name or q in phone:
                matched.append((r, bk))

        st.markdown("---")
        st.markdown("**Kết quả tìm khách đặt trước:**")
        if not matched:
            st.caption("Không tìm thấy khách phù hợp.")
        else:
            for r, bk in matched:
                st.markdown(
                    f"- Phòng **{r['id']}** – {bk.get('customer_name','')} ({bk.get('customer_phone','')})"
                )

# --- 3. VẼ SƠ ĐỒ PHÒNG (GRID) ---
if rooms:
    # ... (CSS styles) ...
    
    # 1. Lọc phòng theo bộ lọc
    filtered_rooms = [r for r in rooms if not filter_floor or str(r.get('floor', '')) in filter_floor]
    
    if not filtered_rooms:
        st.info("Không tìm thấy phòng phù hợp với bộ lọc.")
    else:
        # ... (Group by area) ...
        unique_areas = sorted(list(set([str(r.get('floor', 'Khác') or 'Khác') for r in filtered_rooms])))
        
        for area in unique_areas:
            # ...
            area_rooms = [r for r in filtered_rooms if str(r.get('floor', 'Khác') or 'Khác') == area]
            area_rooms.sort(key=lambda x: x['id'])
            
            # ... (Header) ...
            
            cols = st.columns(4)
            for i, room in enumerate(area_rooms):
                col = cols[i % 4]
                with col:
                    status = room.get('status', RoomStatus.AVAILABLE)
                    icon, bg_color, border_style, label = get_status_style(status)
                    
                    # ... (Card HTML) ...
                    st.markdown(f"""
                    <div style="
                        background-color: {bg_color}; 
                        {border_style}
                        border-radius: 8px; 
                        padding: 10px; 
                        text-align: center; 
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                        margin-bottom: 10px;
                        height: 100%;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        align-items: center;
                    ">
                        <div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 5px; color: #333;">{room['id']}</div>
                        <div style="font-size: 0.85rem; color: #555; margin-bottom: 8px; line-height: 1.3; min-height: 2.4em; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                            {type_map.get(room['room_type_code'], room['room_type_code'])}
                        </div>
                        <div style="font-weight: 600; font-size: 0.9rem; margin-top: auto; padding-top: 5px; border-top: 1px dashed rgba(0,0,0,0.1); width: 100%;">
                            {icon} <span style="margin-left: 5px;">{label}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Nút thao tác nhanh
                    with st.popover("Thao tác", width='stretch'):
                        st.write(f"**Phòng {room['id']}**")
                        st.caption(f"Trạng thái: {status}")

                        booking_info = None
                        booking_id = room.get("current_booking_id")
                        if booking_id:
                            # Use cached map
                            booking_info = active_bookings_map.get(booking_id)

                        if status == RoomStatus.AVAILABLE:
                            if st.button("🛎️ Booking", key=f"booking_{room['id']}", width='stretch'):
                                st.session_state["prefill_room_id"] = room["id"]
                                try:
                                    st.switch_page("pages/2_Booking.py")
                                except Exception:
                                    st.info("Vui lòng truy cập menu Booking.")

                        elif status == RoomStatus.OCCUPIED:
                            if booking_info:
                                with st.expander("👁 Thông tin khách", expanded=True):
                                    st.write(f"**{booking_info.get('customer_name', '')}**")
                                    st.write(f"Check-in: {booking_info.get('check_in').strftime('%d/%m %H:%M') if booking_info.get('check_in') else ''}")
                            
                            c_yes, c_no = st.columns(2)
                            if c_yes.button("Trả phòng", key=f"co_yes_{room['id']}", type="primary", width='stretch'):
                                st.session_state["prefill_checkout_room_id"] = room["id"]
                                try:
                                    st.switch_page("pages/3_Checkout.py")
                                except Exception:
                                    st.info("Vui lòng truy cập menu Trả phòng.")

                        elif status == RoomStatus.RESERVED:
                            st.info("Đã đặt trước.")
                            if booking_info:
                                with st.expander("👁 Thông tin khách", expanded=True):
                                    st.write(f"**{booking_info.get('customer_name', '')}**")
                                    st.write(f"Dự kiến: {booking_info.get('check_in').strftime('%d/%m %H:%M') if booking_info.get('check_in') else ''}")

                            if st.button("Check-in ngay", key=f"checkin_{room['id']}", type="primary", width='stretch'):
                                ok, msg = check_in_reserved_room(room["id"])
                                if ok:
                                    st.success(f"Đã check-in {room['id']}!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        
                        elif status == RoomStatus.DIRTY:
                            if st.button("🧹 Dọn xong", key=f"clean_{room['id']}", width='stretch'):
                                from src.db import update_room_status
                                update_room_status(room['id'], RoomStatus.AVAILABLE)
                                st.rerun()
            # Divider removed for compact UI

else:
    st.info("Chưa có dữ liệu phòng. Vui lòng vào trang Settings để tạo.")