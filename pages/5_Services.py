import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

from src.models import ServiceItem, ServiceCategory, ServiceOrder, RoomStatus, Permission
from src.db import (
    get_all_services, save_service, delete_service,
    get_occupied_rooms, add_service_order, get_orders_by_booking,
    get_all_rooms, get_recent_service_orders
)
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, require_permission, has_permission

# --- CONFIG & LAYOUT ---
st.set_page_config(page_title="Dịch vụ & Ăn uống", layout="wide")

require_login()
require_permission(Permission.VIEW_SERVICES)

apply_sidebar_style()
create_custom_sidebar_menu()

st.title("🍽️ Dịch vụ phòng & Ăn uống")

# --- TABS ---
tab_order, tab_menu, tab_history = st.tabs(["🛒 Đặt món (Order)", "📋 Quản lý Menu", "📜 Lịch sử Order"])

# ---------------------------------------------------------
# TAB 1: ĐẶT MÓN (Cho nhân viên)
# ---------------------------------------------------------
with tab_order:
    # Init cart
    if "cart" not in st.session_state:
        st.session_state["cart"] = {}
    if "svc_page" not in st.session_state:
        st.session_state["svc_page"] = 0

    ITEMS_PER_PAGE = 10

    c_left, c_right = st.columns([1.2, 1], gap="large")

    # ===================== CỘT TRÁI: Phòng + Giỏ hàng =====================
    with c_left:
        # --- 1. Chọn Phòng ---
        st.subheader("1. Chọn Phòng")
        occupied = get_occupied_rooms()
        s_room_id = None
        if not occupied:
            st.warning("Hiện không có phòng nào đang có khách (Occupied).")
        else:
            room_opts = {r['id']: f"{r['id']} - {r.get('floor','Unknown')}" for r in occupied}
            if "selected_room_id" not in st.session_state:
                st.session_state["selected_room_id"] = list(room_opts.keys())[0] if room_opts else None

            s_room_id = st.selectbox(
                "Chọn phòng cần gọi món:",
                options=list(room_opts.keys()),
                format_func=lambda x: room_opts[x],
                index=None,
                placeholder="-- Mời bạn chọn phòng --",
                key="sel_room_order"
            )
            if s_room_id:
                room_data = next((r for r in occupied if r['id'] == s_room_id), None)
                if room_data:
                    bk_id = room_data.get("current_booking_id")
                    st.info(f"Booking ID: `{bk_id}`")
                    st.session_state["current_ordering_bk_id"] = bk_id

        st.markdown("---")

        # --- 2. Giỏ hàng ---
        with st.container(border=True):
            st.subheader("🛒 Giỏ hàng")
            cart = st.session_state.get("cart", {})

            if not cart:
                st.caption("Chưa chọn món nào.")
                total_order = 0
            else:
                total_order = 0
                for iid, data in list(cart.items()):
                    sub = data['price'] * data['qty']
                    total_order += sub

                    cc1, cc2, cc3, cc4 = st.columns([3, 1.2, 1.5, 0.5], gap="small")
                    cc1.write(f"{data['name']}")

                    new_qty = cc2.number_input(
                        "SL", min_value=1, value=data['qty'], key=f"qty_{iid}", label_visibility="collapsed"
                    )
                    if new_qty != data['qty']:
                        cart[iid]['qty'] = new_qty
                        st.rerun()

                    cc3.write(f"{sub:,.0f}")
                    if cc4.button("x", key=f"del_cart_{iid}"):
                        del cart[iid]
                        st.rerun()

                st.divider()
                st.markdown(f"### Tổng: :red[{total_order:,.0f} đ]")

            note = st.text_input("Ghi chú (Không cay, ít đá...)", key="order_note")

            if st.button("✅ Gửi Order / Báo Bếp", type="primary", use_container_width=True):
                if not has_permission(Permission.CREATE_SERVICE_ORDER):
                    st.error("⛔ Bạn không có quyền tạo order.")
                elif not s_room_id:
                    st.error("Chưa chọn phòng!")
                elif not cart:
                    st.error("Giỏ hàng trống!")
                else:
                    bk_id = st.session_state.get("current_ordering_bk_id")
                    items_list = []
                    for iid, data in cart.items():
                        items_list.append({
                            "id": iid,
                            "name": data['name'],
                            "price": data['price'],
                            "qty": data['qty'],
                            "total": data['price'] * data['qty']
                        })

                    new_order = ServiceOrder(
                        booking_id=bk_id,
                        room_id=s_room_id,
                        items=items_list,
                        total_value=total_order,
                        note=note
                    )
                    add_service_order(new_order.to_dict())
                    st.success(f"Đã gọi món cho phòng {s_room_id} thành công!")
                    st.session_state["cart"] = {}
                    st.rerun()

    # ===================== CỘT PHẢI: Chọn Món/Dịch vụ =====================
    with c_right:
        st.subheader("2. Chọn Món/Dịch vụ")

        menu = get_all_services()
        if not menu:
            st.warning("Chưa có menu. Vui lòng sang tab 'Quản lý Menu' để thêm món.")
        else:
            # --- Tìm kiếm + Danh mục ---
            sc1, sc2 = st.columns([1, 2])
            search_q = sc1.text_input("🔍 Tìm kiếm", placeholder="Nhập tên món...", key="svc_search", label_visibility="collapsed")
            cats = [c.value for c in ServiceCategory]
            sel_cat = sc2.radio("Danh mục:", ["Tất cả"] + cats, horizontal=True, label_visibility="collapsed")

            # Filter
            filtered_menu = menu if sel_cat == "Tất cả" else [m for m in menu if m['category'] == sel_cat]

            # Search filter
            if search_q:
                search_q_lower = search_q.lower()
                filtered_menu = [m for m in filtered_menu if search_q_lower in m['name'].lower()]

            if not filtered_menu:
                st.caption("Không có món nào phù hợp.")
            else:
                # --- Pagination ---
                total_items = len(filtered_menu)
                total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

                # Reset page nếu thay đổi filter
                if st.session_state["svc_page"] >= total_pages:
                    st.session_state["svc_page"] = 0

                current_page = st.session_state["svc_page"]
                start_idx = current_page * ITEMS_PER_PAGE
                end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
                page_items = filtered_menu[start_idx:end_idx]

                # Header
                st.caption(f"Hiển thị {start_idx + 1}–{end_idx} / {total_items} món")

                # --- Danh sách món ---
                for item in page_items:
                    c1, c2, c3 = st.columns([2.5, 1.0, 1.2], gap="small")
                    c1.markdown(f"<p style='margin: 0; padding: 3px 0;'><b>{item['name']}</b> ({item['unit']})</p>", unsafe_allow_html=True)
                    c2.markdown(f"<p style='margin: 0; padding: 3px 0;'>{item['price']:,.0f} đ</p>", unsafe_allow_html=True)
                    with c3:
                        if st.button("Thêm món", key=f"add_{item['id']}", use_container_width=True):
                            if not s_room_id:
                                st.toast("Vui lòng chọn phòng", icon="⚠️")
                            else:
                                cart = st.session_state["cart"]
                                if item['id'] in cart:
                                    cart[item['id']]['qty'] += 1
                                else:
                                    cart[item['id']] = {
                                        "id": item['id'],
                                        "name": item['name'],
                                        "price": item['price'],
                                        "qty": 1
                                    }
                                st.toast(f"Đã thêm {item['name']}", icon="🛒")
                    st.markdown("<hr style='margin: 2px 0; border: none; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)

                # --- Nút phân trang ---
                if total_pages > 1:
                    pg_cols = st.columns([1, 3, 1])
                    with pg_cols[0]:
                        if st.button("◀ Trước", disabled=(current_page == 0), key="svc_prev", use_container_width=True):
                            st.session_state["svc_page"] -= 1
                            st.rerun()
                    pg_cols[1].markdown(f"<p style='text-align:center; padding: 8px 0;'>Trang <b>{current_page + 1}</b> / {total_pages}</p>", unsafe_allow_html=True)
                    with pg_cols[2]:
                        if st.button("Sau ▶", disabled=(current_page >= total_pages - 1), key="svc_next", use_container_width=True):
                            st.session_state["svc_page"] += 1
                            st.rerun()


# ---------------------------------------------------------
# TAB 2: QUẢN LÝ MENU (Admin/Manager)
# ---------------------------------------------------------
with tab_menu:
    # Check permisison (Optional: Manager/Admin only?)
    # For now allow all staff to edit menu for simplicity or restriction?
    # Let's restrict to Admin/Manager
    if not has_permission(Permission.MANAGE_SERVICES):
        st.warning("🔒 Chỉ Quản lý mới được chỉnh sửa Menu.")
    else:
        cm_left, cm_right = st.columns([1, 2])
        
        # Form Add/Edit
        with cm_left:
            with st.container(border=True):
                st.subheader("➕ Thêm / Sửa Món")
                
                if "edit_service" not in st.session_state:
                    st.session_state["edit_service"] = None
                
                edit_sv = st.session_state["edit_service"]
                
                is_edit = edit_sv is not None
                
                # Defaults
                d_name = edit_sv['name'] if is_edit else ""
                d_cat = edit_sv['category'] if is_edit else ServiceCategory.DRINK
                d_price = edit_sv['price'] if is_edit else 30000.0
                d_unit = edit_sv['unit'] if is_edit else "ly"
                
                with st.form("frm_service"):
                    s_name = st.text_input("Tên món/Dịch vụ", value=d_name)
                    s_cat = st.selectbox(
                        "Danh mục", 
                        options=[c.value for c in ServiceCategory],
                        index=[c.value for c in ServiceCategory].index(d_cat) if isinstance(d_cat, str) else 0
                    )
                    
                    c_p, c_u = st.columns(2)
                    s_price = c_p.number_input("Giá bán", min_value=0.0, value=float(d_price), step=1000.0)
                    s_unit = c_u.text_input("Đơn vị", value=d_unit)
                    
                    btn_txt = "Cập nhật" if is_edit else "Thêm mới"
                    if st.form_submit_button(btn_txt, type="primary"):
                        if not s_name:
                            st.error("Tên không được để trống")
                        else:
                            sv_obj = ServiceItem(
                                id=edit_sv['id'] if is_edit else None,
                                name=s_name,
                                category=s_cat,
                                price=s_price,
                                unit=s_unit
                            )
                            save_service(sv_obj.to_dict())
                            st.toast(f"Đã lưu {s_name}!", icon="💾")
                            st.session_state["edit_service"] = None
                            st.rerun()
                
                if is_edit:
                    if st.button("Hủy sửa"):
                        st.session_state["edit_service"] = None
                        st.rerun()

        # List Menu
        with cm_right:
            st.subheader("📋 Danh sách Menu")
            full_menu = get_all_services()
            
            if full_menu:
                # Table style
                df = pd.DataFrame(full_menu)
                # Rename cols for display
                # st.dataframe(df[["name", "category", "price", "unit"]]) 
                
                # Custom list for actions
                for svg in full_menu:
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                    c1.write(f"**{svg['name']}**")
                    c2.write(f"{svg['category']}")
                    c3.write(f"{svg['price']:,.0f}/{svg['unit']}")
                    
                    with c4:
                        b_e, b_d = st.columns(2)
                        if b_e.button("✏️", key=f"e_sv_{svg['id']}"):
                            st.session_state["edit_service"] = svg
                            st.rerun()
                        if b_d.button("🗑️", key=f"d_sv_{svg['id']}"):
                            delete_service(svg['id'])
                            st.rerun()
                    st.divider()

# ---------------------------------------------------------
# TAB 3: LỊCH SỬ (Simple View)
# ---------------------------------------------------------
with tab_history:
    st.subheader("📜 Nhật ký Order (20 đơn gần nhất)")
    
    orders = get_recent_service_orders(limit=20)
    
    if not orders:
        st.info("Chưa có order nào được ghi nhận.")
    else:
        for idx, o in enumerate(orders):
            # Format time
            ts = o.get("created_at")
            t_str = ts.strftime("%H:%M %d/%m/%Y") if isinstance(ts, datetime) else "N/A"
            
            # Title: Time - Room - Total
            title = f"{t_str} | Phòng: **{o.get('room_id')}** | Tổng: :red[**{o.get('total_value', 0):,.0f} đ**]"
            
            with st.expander(title, expanded=(idx == 0)):
                st.caption(f"Booking ID: {o.get('booking_id')}")
                st.write("**Chi tiết món:**")
                for item in o.get("items", []):
                    st.write(f"- {item['name']} ({item['price']:,.0f}) x{item['qty']} = **{item['total']:,.0f} đ**")
                
                if o.get("note"):
                    st.info(f"Ghi chú: {o.get('note')}")
