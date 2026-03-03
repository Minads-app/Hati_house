import base64
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

# Nhớ import thêm save_room_to_db, get_all_rooms, delete_room ở đầu file
from src.db import (
    delete_room,
    delete_room_type,
    get_all_room_types,
    get_all_rooms,
    save_payment_config,
    save_room_to_db,
    save_room_type_to_db,
    get_payment_config,
    get_system_config,
    save_system_config,
    create_user,
    delete_user,
    hash_password,
    get_db,
    get_all_users,
    get_user,
    update_user_password,
    get_all_role_permissions,
    save_role_permissions,
    init_default_permissions,
    get_resort_name,
)
from src.models import Room, RoomStatus, PriceConfig, RoomType, User, UserRole, Permission, PERMISSION_METADATA
from src.ui import apply_sidebar_style, create_custom_sidebar_menu, require_login, has_permission
from src.config import AppConfig
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Cấu hình hệ thống", layout="wide")

require_login()

apply_sidebar_style()
create_custom_sidebar_menu()

st.title(f"⚙️ Cấu hình {get_resort_name()}")

# Sử dụng Tabs để phân chia khu vực quản lý
tab_types, tab_special_days, tab_rooms, tab_system, tab_staff, tab_permissions = st.tabs(
    ["🏨 Loại Phòng & Giá", "📅 Cấu hình Lễ/Tết & Cuối tuần", "🛏️ Danh sách Phòng", "🛠️ Hệ thống", "👥 Nhân viên", "🔐 Phân quyền"]
)

# --- TAB 1: QUẢN LÝ LOẠI PHÒNG ---

# --- Helper: Input giá tiền có dấu phân cách hàng nghìn ---
import streamlit.components.v1 as components

def price_input(label, value=0, key=None, container=None):
    """Input giá VND với dấu phân cách hàng nghìn. Trả về int."""
    target = container or st
    display = f"{int(value):,}" if value else "0"
    raw = target.text_input(label, value=display, key=key)
    try:
        clean = raw.replace(",", "").replace(".", "").replace(" ", "").strip()
        return int(clean) if clean else 0
    except (ValueError, TypeError):
        return int(value) if value else 0

# --- JS: Tự động format số khi đang nhập ---
components.html("""
<script>
(function() {
    const doc = window.parent.document;
    let formatting = false;

    function formatNum(n) {
        return n.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
    }

    function handleInput(input) {
        if (formatting) return;
        
        // 1. Check Keywords in Label (aria-label)
        const label = (input.getAttribute('aria-label') || '').toLowerCase();
        const skipKeywords = ['điện thoại', 'phone', 'sđt', 'mật khẩu', 'password', 'tài khoản', 'account', 'mã', 'id', 'cccd', 'cmnd'];
        if (skipKeywords.some(kw => label.includes(kw))) return;

        const raw = input.value.replace(/[,\\s]/g, '');
        if (!/^\\d*$/.test(raw) || raw === '') return;

        // 2. Check leading zero (Save phone numbers if keyword check fails)
        if (raw.length > 1 && raw.startsWith('0')) return;

        const formatted = raw === '0' ? '0' : formatNum(raw.replace(/^0+/, '') || '0');
        if (formatted === input.value) return;

        const pos = input.selectionStart;
        const oldLen = input.value.length;

        formatting = true;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(input, formatted);
        input.dispatchEvent(new Event('input', { bubbles: true }));

        const newLen = input.value.length;
        const newPos = Math.max(0, pos + (newLen - oldLen));
        input.setSelectionRange(newPos, newPos);
        formatting = false;
    }

    function setup() {
        doc.querySelectorAll('input[type="text"]').forEach(input => {
            if (input.dataset.priceFmt) return;
            
            // Initial Check for Skip
            const label = (input.getAttribute('aria-label') || '').toLowerCase();
            const skipKeywords = ['điện thoại', 'phone', 'sđt', 'mật khẩu', 'password', 'tài khoản', 'account', 'mã', 'id', 'cccd', 'cmnd'];
            if (skipKeywords.some(kw => label.includes(kw))) {
                input.dataset.priceFmt = 'skipped'; // Mark as checked/skipped
                return;
            }

            // Chỉ format ô có nội dung là số thuần
            const clean = input.value.replace(/[,\\s]/g, '');
            if (!/^\\d+$/.test(clean)) return;

            // Check leading zero
            if (clean.length > 1 && clean.startsWith('0')) return;

            input.dataset.priceFmt = '1';
            input.addEventListener('input', () => handleInput(input));
            handleInput(input);
        });
    }

    setInterval(setup, 800);
    setup();
})();
</script>
""", height=0)


# --- Dialog thêm loại phòng mới ---
@st.dialog("➕ Thêm Loại Phòng Mới", width="large")
def dialog_add_room_type():
    with st.form("frm_add_room_type"):
        c1, c2 = st.columns(2)
        r_name = c1.text_input("Tên loại phòng", placeholder="VD: Phòng Đơn")
        r_code = c2.text_input("Mã (ID)", placeholder="VD: STD").upper().strip()
        
        c3, c4 = st.columns(2)
        r_adults = c3.number_input("Người lớn mặc định", 1, 10, 2)
        r_kids = c4.number_input("Trẻ em mặc định", 0, 10, 0)
        
        st.markdown("---")
        st.markdown("##### 💰 Thiết lập Giá (VND)")
        
        # Header
        hd1, hd2, hd3, hd4 = st.columns([1.5, 1, 1, 1])
        hd1.markdown("**Hạng mục**")
        hd2.markdown("**Ngày thường**")
        hd3.markdown("**Cuối tuần**")
        hd4.markdown("**Lễ/Tết**")
        
        # Giá ngày
        st.markdown("###### 📅 1. Giá ngày (24h)")
        c1, c2, c3 = st.columns(3)
        d_n = price_input("Thường", 500000, "add_dn", c1)
        d_w = price_input("C.tuần", 0, "add_dw", c2)
        d_h = price_input("Lễ/Tết", 0, "add_dh", c3)
        
        # Qua đêm
        st.markdown("---")
        st.markdown("###### 🌙 2. Qua đêm")
        c1, c2, c3 = st.columns(3)
        o_n = price_input("Thường", 300000, "add_on", c1)
        o_w = price_input("C.tuần", 0, "add_ow", c2)
        o_h = price_input("Lễ/Tết", 0, "add_oh", c3)
        
        # Theo giờ
        st.markdown("---")
        st.markdown("###### ⏱️ 3. Theo giờ")
        st.caption("1 giờ đầu")
        c1, c2, c3 = st.columns(3)
        h1_n = price_input("Thường", 50000, "add_h1n", c1)
        h1_w = price_input("C.tuần", 0, "add_h1w", c2)
        h1_h = price_input("Lễ/Tết", 0, "add_h1h", c3)
        
        # 2h
        st.caption("2 giờ đầu")
        c1, c2, c3 = st.columns(3)
        h2_n = price_input("Thường", 90000, "add_h2n", c1)
        h2_w = price_input("C.tuần", 0, "add_h2w", c2)
        h2_h = price_input("Lễ/Tết", 0, "add_h2h", c3)
        
        # 3h
        st.caption("3 giờ đầu")
        c1, c2, c3 = st.columns(3)
        h3_n = price_input("Thường", 120000, "add_h3n", c1)
        h3_w = price_input("C.tuần", 0, "add_h3w", c2)
        h3_h = price_input("Lễ/Tết", 0, "add_h3h", c3)
        
        # Mỗi giờ tiếp
        st.caption("Mỗi giờ tiếp theo (+)")
        c1, c2, c3 = st.columns(3)
        hn_n = price_input("Thường (+)", 20000, "add_hnn", c1)
        hn_w = price_input("C.tuần (+)", 0, "add_hnw", c2)
        hn_h = price_input("Lễ/Tết (+)", 0, "add_hnh", c3)
        
        st.markdown("---")
        st.markdown("**⚙️ Cho phép đặt**")
        c1, c2, c3 = st.columns(3)
        en_hourly = c1.checkbox("Theo giờ", value=True, key="add_eh")
        en_overnight = c2.checkbox("Qua đêm", value=True, key="add_eo")
        en_daily = c3.checkbox("Theo ngày", value=True, key="add_ed")
        
        submitted = st.form_submit_button("➕ Thêm Mới", type="primary", use_container_width=True)
        
        if submitted:
            if not r_code or not r_name:
                st.error("Vui lòng nhập Mã và Tên phòng!")
            else:
                def _build(d, o, h1, h2, h3, hn, en_h, en_o, en_d):
                    return PriceConfig(
                        daily_price=float(d), overnight_price=float(o),
                        hourly_blocks={"1": h1, "2": h2, "3": h3, "4": h3 + hn},
                        enable_hourly=en_h, enable_overnight=en_o, enable_daily=en_d
                    )
                
                pc_main = _build(d_n, o_n, h1_n, h2_n, h3_n, hn_n, en_hourly, en_overnight, en_daily)
                pc_week = _build(d_w, o_w, h1_w, h2_w, h3_w, hn_w, en_hourly, en_overnight, en_daily) if (d_w or o_w or h1_w) else None
                pc_holi = _build(d_h, o_h, h1_h, h2_h, h3_h, hn_h, en_hourly, en_overnight, en_daily) if (d_h or o_h or h1_h) else None
                
                new_type = RoomType(
                    type_code=r_code, name=r_name,
                    default_adults=r_adults, default_children=r_kids,
                    pricing=pc_main, pricing_weekend=pc_week, pricing_holiday=pc_holi
                )
                try:
                    save_room_type_to_db(new_type.to_dict())
                    st.toast(f"✅ Thêm mới {r_name} thành công!", icon="🎉")
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")

with tab_types:
    # Nút thêm mới (mở dialog)
    if st.button("➕ Thêm Loại Phòng Mới", type="primary", use_container_width=False):
        dialog_add_room_type()
    
    st.markdown("---")
    
    # --- Danh sách hiển thị (Full width) ---
    st.subheader("📋 Danh sách Loại phòng")
    
    room_types_data = get_all_room_types()
    
    # Session state cho inline edit
    if "inline_edit_type" not in st.session_state:
        st.session_state["inline_edit_type"] = None
    
    if room_types_data:
        for item in room_types_data:
            tc = item['type_code']
            pricing = item.get('pricing', {})
            p_weekend = item.get('pricing_weekend') or {}
            p_holiday = item.get('pricing_holiday') or {}
            blocks = pricing.get('hourly_blocks', {})
            blocks_w = p_weekend.get('hourly_blocks', {}) if p_weekend else {}
            blocks_h = p_holiday.get('hourly_blocks', {}) if p_holiday else {}
            
            is_inline_edit = (st.session_state["inline_edit_type"] == tc)
            
            with st.expander(f"**{item['name']} ({tc})** - {pricing.get('daily_price', 0):,.0f} đ/ngày", expanded=is_inline_edit):
                
                if is_inline_edit:
                    # ========== CHẾ ĐỘ SỬA INLINE ==========
                    with st.form(f"frm_inline_{tc}"):
                        st.markdown("##### ✏️ Đang chỉnh sửa")
                        
                        c1, c2 = st.columns(2)
                        e_name = c1.text_input("Tên loại phòng", value=item.get('name', ''), key=f"ie_name_{tc}")
                        c2.text_input("Mã (ID)", value=tc, disabled=True, key=f"ie_code_{tc}")
                        
                        c3, c4 = st.columns(2)
                        e_adults = c3.number_input("Người lớn", 1, 10, item.get('default_adults', 2), key=f"ie_adults_{tc}")
                        e_kids = c4.number_input("Trẻ em", 0, 10, item.get('default_children', 0), key=f"ie_kids_{tc}")
                        
                        st.markdown("---")
                        
                        def _v(d, key, default=0):
                            return int(d.get(key, default))
                        def _b(blk, key, default=0):
                            return int(blk.get(key, default))
                        def _next(blk):
                            if blk.get('4') and blk.get('3'):
                                d = int(blk['4']) - int(blk['3'])
                                return d if d > 0 else 20000
                            return 20000
                        
                        hd1, hd2, hd3, hd4 = st.columns([1.5, 1, 1, 1])
                        hd1.markdown("**Hạng mục**")
                        hd2.markdown("**Ngày thường**")
                        hd3.markdown("**Cuối tuần**")
                        hd4.markdown("**Lễ/Tết**")
                        
                        st.markdown("###### 📅 1. Giá ngày (24h)")
                        c1, c2, c3 = st.columns(3)
                        e_d_n = price_input("Thường", _v(pricing, 'daily_price', 500000), f"ie_dn_{tc}", c1)
                        e_d_w = price_input("C.tuần", _v(p_weekend, 'daily_price'), f"ie_dw_{tc}", c2)
                        e_d_h = price_input("Lễ/Tết", _v(p_holiday, 'daily_price'), f"ie_dh_{tc}", c3)
                        
                        st.markdown("---")
                        st.markdown("###### 🌙 2. Qua đêm")
                        c1, c2, c3 = st.columns(3)
                        e_o_n = price_input("Thường", _v(pricing, 'overnight_price', 300000), f"ie_on_{tc}", c1)
                        e_o_w = price_input("C.tuần", _v(p_weekend, 'overnight_price'), f"ie_ow_{tc}", c2)
                        e_o_h = price_input("Lễ/Tết", _v(p_holiday, 'overnight_price'), f"ie_oh_{tc}", c3)
                        
                        st.markdown("---")
                        st.markdown("###### ⏱️ 3. Theo giờ")
                        st.caption("1 giờ đầu")
                        c1, c2, c3 = st.columns(3)
                        e_h1_n = price_input("Thường", _b(blocks, '1', 50000), f"ie_h1n_{tc}", c1)
                        e_h1_w = price_input("C.tuần", _b(blocks_w, '1'), f"ie_h1w_{tc}", c2)
                        e_h1_h = price_input("Lễ/Tết", _b(blocks_h, '1'), f"ie_h1h_{tc}", c3)
                        
                        st.caption("2 giờ đầu")
                        c1, c2, c3 = st.columns(3)
                        e_h2_n = price_input("Thường", _b(blocks, '2', 90000), f"ie_h2n_{tc}", c1)
                        e_h2_w = price_input("C.tuần", _b(blocks_w, '2'), f"ie_h2w_{tc}", c2)
                        e_h2_h = price_input("Lễ/Tết", _b(blocks_h, '2'), f"ie_h2h_{tc}", c3)
                        
                        st.caption("3 giờ đầu")
                        c1, c2, c3 = st.columns(3)
                        e_h3_n = price_input("Thường", _b(blocks, '3', 120000), f"ie_h3n_{tc}", c1)
                        e_h3_w = price_input("C.tuần", _b(blocks_w, '3'), f"ie_h3w_{tc}", c2)
                        e_h3_h = price_input("Lễ/Tết", _b(blocks_h, '3'), f"ie_h3h_{tc}", c3)
                        
                        st.caption("Mỗi giờ tiếp theo (+)")
                        c1, c2, c3 = st.columns(3)
                        e_hn_n = price_input("Thường (+)", _next(blocks), f"ie_hnn_{tc}", c1)
                        e_hn_w = price_input("C.tuần (+)", _next(blocks_w) if blocks_w else 20000, f"ie_hnw_{tc}", c2)
                        e_hn_h = price_input("Lễ/Tết (+)", _next(blocks_h) if blocks_h else 20000, f"ie_hnh_{tc}", c3)
                        
                        st.markdown("---")
                        st.markdown("**⚙️ Cho phép đặt**")
                        c1, c2, c3 = st.columns(3)
                        e_en_hourly = c1.checkbox("Theo giờ", value=pricing.get('enable_hourly', True), key=f"ie_eh_{tc}")
                        e_en_overnight = c2.checkbox("Qua đêm", value=pricing.get('enable_overnight', True), key=f"ie_eo_{tc}")
                        e_en_daily = c3.checkbox("Theo ngày", value=pricing.get('enable_daily', True), key=f"ie_ed_{tc}")
                        
                        st.markdown("---")
                        c_save, c_cancel = st.columns(2)
                        btn_save = c_save.form_submit_button("💾 Lưu thay đổi", type="primary", use_container_width=True)
                        btn_cancel = c_cancel.form_submit_button("❌ Hủy", use_container_width=True)
                        
                        if btn_save:
                            def _build_pc(d, o, h1, h2, h3, hn, en_h, en_o, en_d):
                                return PriceConfig(
                                    daily_price=float(d), overnight_price=float(o),
                                    hourly_blocks={"1": h1, "2": h2, "3": h3, "4": h3 + hn},
                                    enable_hourly=en_h, enable_overnight=en_o, enable_daily=en_d
                                )
                            
                            pc_main = _build_pc(e_d_n, e_o_n, e_h1_n, e_h2_n, e_h3_n, e_hn_n, e_en_hourly, e_en_overnight, e_en_daily)
                            pc_week = _build_pc(e_d_w, e_o_w, e_h1_w, e_h2_w, e_h3_w, e_hn_w, e_en_hourly, e_en_overnight, e_en_daily) if (e_d_w or e_o_w or e_h1_w) else None
                            pc_holi = _build_pc(e_d_h, e_o_h, e_h1_h, e_h2_h, e_h3_h, e_hn_h, e_en_hourly, e_en_overnight, e_en_daily) if (e_d_h or e_o_h or e_h1_h) else None
                            
                            updated = RoomType(
                                type_code=tc, name=e_name,
                                default_adults=e_adults, default_children=e_kids,
                                pricing=pc_main, pricing_weekend=pc_week, pricing_holiday=pc_holi
                            )
                            try:
                                save_room_type_to_db(updated.to_dict())
                                st.toast(f"✅ Đã cập nhật {e_name}!", icon="🎉")
                                st.session_state["inline_edit_type"] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lỗi: {e}")
                        
                        if btn_cancel:
                            st.session_state["inline_edit_type"] = None
                            st.rerun()
                
                else:
                    # ========== CHẾ ĐỘ XEM ==========
                    c_info1, c_info2 = st.columns(2)
                    c_info1.write(f"👤 Người lớn: **{item.get('default_adults', 2)}**")
                    c_info2.write(f"👶 Trẻ em: **{item.get('default_children', 0)}**")
                    
                    modes = []
                    if pricing.get('enable_hourly', True): modes.append("Giờ")
                    if pricing.get('enable_overnight', True): modes.append("Qua đêm")
                    if pricing.get('enable_daily', True): modes.append("Ngày")
                    st.caption(f"✅ Cho phép: **{', '.join(modes)}**")
                    
                    st.markdown("---")
                    
                    def fmt(val):
                        if not val: return "-"
                        return f"{float(val):,.0f}"
                    
                    hd1, hd2, hd3, hd4 = st.columns([1.5, 1, 1, 1])
                    hd1.markdown("**Hạng mục**")
                    hd2.markdown("**Ngày thường**")
                    hd3.markdown("**Cuối tuần**")
                    hd4.markdown("**Lễ/Tết**")
                    
                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("📅 Giá ngày (24h)")
                    r2.write(f"**{fmt(pricing.get('daily_price'))}**")
                    r3.write(fmt(p_weekend.get('daily_price')))
                    r4.write(fmt(p_holiday.get('daily_price')))
                    
                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("🌙 Qua đêm")
                    r2.write(f"**{fmt(pricing.get('overnight_price'))}**")
                    r3.write(fmt(p_weekend.get('overnight_price')))
                    r4.write(fmt(p_holiday.get('overnight_price')))
                    
                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("⏱️ 1 giờ đầu")
                    r2.write(f"**{fmt(blocks.get('1'))}**")
                    r3.write(fmt(blocks_w.get('1')))
                    r4.write(fmt(blocks_h.get('1')))

                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("⏱️ 2 giờ đầu")
                    r2.write(f"**{fmt(blocks.get('2'))}**")
                    r3.write(fmt(blocks_w.get('2')))
                    r4.write(fmt(blocks_h.get('2')))
                    
                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("⏱️ 3 giờ đầu")
                    r2.write(f"**{fmt(blocks.get('3'))}**")
                    r3.write(fmt(blocks_w.get('3')))
                    r4.write(fmt(blocks_h.get('3')))
                    
                    def calc_next(blk):
                        if blk.get('4') and blk.get('3'):
                            diff = float(blk['4']) - float(blk['3'])
                            return diff if diff > 0 else 0
                        return 0
                    r1, r2, r3, r4 = st.columns([1.5, 1, 1, 1])
                    r1.write("⏱️ Mỗi giờ tiếp (+)")
                    r2.write(f"**{fmt(calc_next(blocks))}**")
                    r3.write(fmt(calc_next(blocks_w)))
                    r4.write(fmt(calc_next(blocks_h)))
                    
                    extra_adult = pricing.get('extra_adult_surcharge', 0)
                    extra_child = pricing.get('extra_child_surcharge', 0)
                    if extra_adult or extra_child:
                        st.markdown("---")
                        st.caption("💰 Phụ thu")
                        r1, r2 = st.columns(2)
                        r1.write(f"Người lớn thêm: **{fmt(extra_adult)}** đ")
                        r2.write(f"Trẻ em thêm: **{fmt(extra_child)}** đ")

                    st.markdown("---")
                    c_edit, c_del = st.columns([1, 1])
                    with c_edit:
                         if st.button("✏️ Sửa", key=f"edit_{tc}", use_container_width=True):
                             st.session_state["inline_edit_type"] = tc
                             st.rerun()
                    
                    with c_del:
                        if st.button("🗑️ Xóa", key=f"del_{tc}", use_container_width=True):
                            delete_room_type(tc)
                            if st.session_state.get("inline_edit_type") == tc:
                                st.session_state["inline_edit_type"] = None
                            st.rerun()
    else:
        st.info("Chưa có loại phòng nào. Hãy bấm nút '➕ Thêm Loại Phòng Mới' ở trên.")

        # --- TAB 2: CẤU HÌNH NGÀY LỄ/TẾT & CUỐI TUẦN ---
with tab_special_days:
    col_weekend, col_holiday = st.columns(2)
    
    # Lấy config hiện tại
    try:
        special_days_cfg = get_system_config("special_days")
    except:
        special_days_cfg = {}
        
    # current_weekends = set(special_days_cfg.get("weekend_days", [])) # OLD LOGIC
    current_holidays = set(special_days_cfg.get("holidays", []))
    current_weekend_weekdays = special_days_cfg.get("weekend_weekdays", [5, 6]) # Default Sat(5), Sun(6)

    # Helper function lưu
    def save_special_days():
        cfg = {
            # "weekend_days": list(current_weekends), # OLD
            "weekend_weekdays": current_weekend_weekdays,
            "holidays": list(current_holidays)
        }
        save_system_config("special_days", cfg)
        st.toast("Đã lưu cấu hình ngày đặc biệt!", icon="💾")

    # 1. Cấu hình Cuối Tuần
    with col_weekend:
        st.subheader("📅 Định nghĩa Cuối Tuần")
        st.caption("Chọn các thứ trong tuần được tính là 'Cuối tuần' (áp dụng cho CẢ NĂM).")
        
        weekday_map = {
            0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5", 
            4: "Thứ 6", 5: "Thứ 7", 6: "Chủ Nhật"
        }
        
        # Multiselect
        selected_days = st.multiselect(
            "Chọn thứ:",
            options=list(weekday_map.keys()),
            format_func=lambda x: weekday_map[x],
            default=current_weekend_weekdays
        )
        
        if st.button("Lưu cấu hình Cuối tuần", type="primary"):
            current_weekend_weekdays = selected_days
            save_special_days()
            st.rerun()

        st.info(f"Đang áp dụng: {', '.join([weekday_map[d] for d in sorted(current_weekend_weekdays)])}")

    # 2. Cấu hình Ngày Lễ
    with col_holiday:
        st.subheader("🎉 Ngày Lễ / Tết")
        st.caption("Danh sách ngày được tính là 'Lễ/Tết' (áp dụng giá Holiday).")
        
        # Load notes
        current_notes = special_days_cfg.get("holiday_notes", {}) # Dict { "YYYY-MM-DD": "Note" }

        # Helper save expanded
        def save_special_days_extended():
            cfg = {
                "weekend_weekdays": current_weekend_weekdays,
                "holidays": list(current_holidays),
                "holiday_notes": current_notes
            }
            save_system_config("special_days", cfg)
            st.toast("Đã lưu cấu hình ngày đặc biệt!", icon="💾")

        # --- FORM THÊM NGÀY ---
        with st.container(border=True):
            st.write("###### ➕ Thêm Ngày Lễ")
            
            tab_single, tab_range, tab_auto = st.tabs(["Chọn Ngày Lẻ", "Chọn Khoảng Ngày", "Tự Động"])
            
            # MODE 1: CHỌN NGÀY LẺ
            with tab_single:
                with st.form("frm_single_day"):
                    st.caption("Chọn một ngày cụ thể (VD: Giỗ tổ 10/3).")
                    d_single = st.date_input("Chọn ngày", value=date.today(), format="DD/MM/YYYY")
                    note_single = st.text_input("Ghi chú (Tùy chọn)", placeholder="VD: Giỗ tổ Hùng Vương")
                    
                    if st.form_submit_button("Thêm Ngay"):
                        d_str = d_single.strftime("%Y-%m-%d")
                        if d_str not in current_holidays:
                            current_holidays.add(d_str)
                            if note_single:
                                current_notes[d_str] = note_single
                            save_special_days_extended()
                            st.rerun()
                        else:
                            st.warning("Ngày này đã có trong danh sách!")
                            # Update note nếu muốn?
                            if note_single:
                                current_notes[d_str] = note_single
                                save_special_days_extended()
                                st.rerun()

            # MODE 2: CHỌN KHOẢNG NGÀY
            with tab_range:
                with st.form("frm_range_day"):
                    st.caption("Chọn Bắt đầu & Kết thúc -> Thêm tất cả ngày ở giữa.")
                    c_start, c_end = st.columns(2)
                    d_start = c_start.date_input("Từ ngày", value=date.today(), format="DD/MM/YYYY")
                    d_end = c_end.date_input("Đến ngày", value=date.today() + timedelta(days=1), format="DD/MM/YYYY")
                    note_range = st.text_input("Ghi chú chung cho khoảng này", placeholder="VD: Nghỉ Tết Nguyên Đán")
                    
                    if st.form_submit_button("Thêm Khoảng"):
                        if d_end < d_start:
                            st.error("Ngày kết thúc phải sau ngày bắt đầu!")
                        else:
                            delta = d_end - d_start
                            added_count = 0
                            for i in range(delta.days + 1):
                                day = d_start + timedelta(days=i)
                                day_str = day.strftime("%Y-%m-%d")
                                current_holidays.add(day_str)
                                if note_range:
                                    current_notes[day_str] = note_range
                                added_count += 1
                            
                            save_special_days_extended()
                            st.success(f"Đã thêm {added_count} ngày vào danh sách!")
                            st.rerun()

            # MODE 3: TỰ ĐỘNG (VN)
            with tab_auto:
                st.caption("Thêm nhanh các ngày lễ cố định của Việt Nam.")
                if st.button("Thêm tự động (2025-2027)", use_container_width=True):
                    holidays_list = []
                    notes_map = {}
                    
                    # 1. Dương lịch
                    years = [2025, 2026, 2027]
                    fixed_dates = {
                        "01-01": "Tết Dương Lịch", 
                        "04-30": "Giải phóng MN", 
                        "05-01": "Quốc tế Lao động", 
                        "09-02": "Quốc khánh"
                    }
                    for y in years:
                        for d, n in fixed_dates.items():
                            full_d = f"{y}-{d}"
                            holidays_list.append(full_d)
                            notes_map[full_d] = n

                    # 2. Âm lịch (Hardcode)
                    lunar_mapped = {
                        2025: [
                            ("2025-01-28", "Tết Nguyên Đán"), ("2025-01-29", "Tết Nguyên Đán"), 
                            ("2025-01-30", "Tết Nguyên Đán"), ("2025-01-31", "Tết Nguyên Đán"), 
                            ("2025-02-01", "Tết Nguyên Đán"), ("2025-04-07", "Giỗ tổ Hùng Vương")
                        ],
                        2026: [
                            ("2026-02-16", "Tết Nguyên Đán"), ("2026-02-17", "Tết Nguyên Đán"),
                            ("2026-02-18", "Tết Nguyên Đán"), ("2026-02-19", "Tết Nguyên Đán"),
                            ("2026-02-20", "Tết Nguyên Đán"), ("2026-04-26", "Giỗ tổ Hùng Vương")
                        ],
                        2027: [
                            ("2027-02-05", "Tết Nguyên Đán"), ("2027-02-06", "Tết Nguyên Đán"),
                            ("2027-02-07", "Tết Nguyên Đán"), ("2027-02-08", "Tết Nguyên Đán"),
                            ("2027-02-09", "Tết Nguyên Đán"), ("2027-04-15", "Giỗ tổ Hùng Vương")
                        ]
                    }
                    
                    for y in years:
                        if y in lunar_mapped:
                            for d_str, note in lunar_mapped[y]:
                                holidays_list.append(d_str)
                                notes_map[d_str] = note

                    count = 0
                    for h in holidays_list:
                        if h not in current_holidays:
                            current_holidays.add(h)
                            current_notes[h] = notes_map.get(h, "")
                            count += 1
                        else:
                            # Update note nếu chưa có
                            if not current_notes.get(h):
                                current_notes[h] = notes_map.get(h, "")
                    
                    save_special_days_extended()
                    st.success(f"Đã thêm {count} ngày Lễ/Tết!")
                    st.rerun()

        # --- DANH SÁCH HIỂN THỊ ---
        st.divider()
        c_tit, c_act = st.columns([2, 1])
        c_tit.write(f"**Danh sách ({len(current_holidays)} ngày):**")
        
        if st.button("🗑️ Xóa TẤT CẢ", type="secondary"):
            current_holidays.clear()
            current_notes.clear()
            save_special_days_extended()
            st.rerun()

        sorted_holidays = sorted(list(current_holidays))
        
        if sorted_holidays:
            # Tạo DataFrame display
            data_display = []
            for d_str in sorted_holidays:
                data_display.append({
                    "Ngày Lễ": d_str,
                    "Ngày hiển thị": pd.to_datetime(d_str).strftime("%d/%m/%Y"),
                    "Ghi chú": current_notes.get(d_str, "")
                })
                
            df_h = pd.DataFrame(data_display)
            
            # Hiển thị bảng có tích chọn
            event_h = st.dataframe(
                df_h[["Ngày hiển thị", "Ghi chú"]], 
                on_select="rerun", 
                selection_mode="multi-row", 
                use_container_width=True,
                height=400
            )

            # Xử lý xóa
            if len(event_h.selection.rows) > 0:
                rows_to_del = [sorted_holidays[i] for i in event_h.selection.rows]
                st.info(f"Đang chọn {len(rows_to_del)} ngày để xóa.")
                
                if st.button("🗑️ Xóa ngày đã chọn", type="primary"):
                    for r in rows_to_del:
                        current_holidays.remove(r)
                        if r in current_notes:
                            del current_notes[r]
                    save_special_days_extended()
                    st.rerun()

    # --- TAB 3: QUẢN LÝ DANH SÁCH PHÒNG ---
with tab_rooms:
    # Lấy danh sách loại phòng để nạp vào Selectbox (Move up to be available for both)
    all_types = get_all_room_types()
    if not all_types:
        st.warning("⚠️ Vui lòng tạo 'Loại phòng' bên Tab 1 trước!")
    else:
        # Tạo dictionary map
        type_options = {t["type_code"]: f"{t['name']} ({t['type_code']})" for t in all_types}
        type_map_simple = {t["type_code"]: t["name"] for t in all_types}

        c_add, c_view = st.columns([1, 2])
        
        # --- STATE MANAGEMENT ---
        if "edit_room" not in st.session_state:
            st.session_state["edit_room"] = None
        
        edit_room_data = st.session_state["edit_room"]
        is_edit_room = edit_room_data is not None

        # 1. Form thêm/sửa phòng
        with c_add:
            with st.container(border=True):
                form_title = f"✏️ Sửa Phòng {edit_room_data['id']}" if is_edit_room else "➕ Thêm Phòng Mới"
                st.subheader(form_title)
                
                # Default values
                d_id = ""
                d_type = list(type_options.keys())[0] if type_options else ""
                d_floor = ""
                d_status = RoomStatus.AVAILABLE
                
                if is_edit_room:
                    d_id = edit_room_data["id"]
                    d_type = edit_room_data["room_type_code"]
                    d_floor = str(edit_room_data.get("floor", ""))
                
                with st.form("frm_room"):
                    # Nếu edit thì không cho sửa ID để tránh lỗi logic, hoặc phải handle delete old -> create new
                    # Đơn giản nhất: Disable ID khi edit
                    r_id = st.text_input("Số phòng", value=d_id, placeholder="101", disabled=is_edit_room).strip()
                    r_type_code = st.selectbox(
                        "Loại phòng",
                        options=list(type_options.keys()),
                        format_func=lambda x: type_options[x],
                        index=list(type_options.keys()).index(d_type) if d_type in type_options else 0
                    )
                    r_floor = st.text_input("Khu vực", value=d_floor, placeholder="VD: Tầng 1, Khu A...").strip()
                    
                    # Thêm chọn trạng thái bảo trì
                    status_opts = [RoomStatus.AVAILABLE, RoomStatus.MAINTENANCE]
                    status_labels = {
                        RoomStatus.AVAILABLE: "✅ Sẵn sàng đón khách",
                        RoomStatus.MAINTENANCE: "🔧 Đang bảo trì / Sửa chữa"
                    }
                    
                    # Nếu đang edit và status hiện tại không nằm trong list trên (VD: OCCUPIED), thêm vào để hiển thị
                    current_stt = edit_room_data.get("status", RoomStatus.AVAILABLE) if is_edit_room else RoomStatus.AVAILABLE
                    if current_stt not in status_opts:
                        status_opts.append(current_stt)
                        status_labels[current_stt] = f"⚠️ {current_stt} (Đang có khách?)"

                    r_status = st.selectbox(
                        "Trạng thái",
                        options=status_opts,
                        format_func=lambda x: status_labels.get(x, x),
                        index=status_opts.index(current_stt) if current_stt in status_opts else 0
                    )

                    btn_lbl = "💾 Cập nhật" if is_edit_room else "Lưu Phòng"
                    if st.form_submit_button(btn_lbl, type="primary"):
                        if r_id:
                            new_room = Room(
                                id=r_id,
                                room_type_code=r_type_code,
                                floor=r_floor or "Khu vực 1",
                                status=r_status, 
                            )
                            # Nếu đang edit, giữ lại các field khác
                            if is_edit_room:
                                new_room.current_booking_id = edit_room_data.get("current_booking_id")
                                new_room.note = edit_room_data.get("note", "")
                                # Nếu status chọn là AVAILABLE, có thể cần clear current_booking_id? 
                                # An toàn: Nếu chuyển sang Maintenance, giữ nguyên booking id (nếu có) để sau này check lại, 
                                # nhưng thường bảo trì là phòng trống. 
                                # Tạm thời chỉ update status.

                            save_room_to_db(new_room.to_dict())
                            msg = "Cập nhật" if is_edit_room else "Thêm mới"
                            st.toast(f"✅ {msg} phòng {r_id} thành công!", icon="🎉")
                            st.session_state["edit_room"] = None
                            st.rerun()
                        else:
                            st.error("Chưa nhập số phòng!")
                
                if is_edit_room:
                    if st.button("❌ Hủy bỏ thay đổi", use_container_width=True):
                        st.session_state["edit_room"] = None
                        st.rerun()

        # 2. Danh sách phòng hiện có
        with c_view:
            st.subheader("📋 Danh sách Phòng")
            rooms = get_all_rooms()
            if rooms:
                # Header row
                # Custom compact header
                headers = st.columns([1, 1.5, 1.5, 1.5, 1.5])
                headers[0].markdown("**Phòng**")
                headers[1].markdown("**Loại**")
                headers[2].markdown("**Khu vực**")
                headers[3].markdown("**Trạng thái**")
                headers[4].markdown("**Thao tác**")
                st.markdown('<hr style="margin: 5px 0; border-top: 1px solid #ddd;">', unsafe_allow_html=True)
                
                # Sort rooms by Area then ID
                rooms.sort(key=lambda x: (str(x.get("floor","")), x["id"]))

                for r in rooms:
                    c1, c2, c3, c4, c5 = st.columns([1, 1.5, 1.5, 1.5, 1.5])
                    c1.write(f"**{r['id']}**")
                    c2.write(type_map_simple.get(r['room_type_code'], r['room_type_code']))
                    c3.write(str(r.get('floor', '')))
                    
                    # Status coloring helper
                    stt = r.get('status', RoomStatus.AVAILABLE)
                    color = "green" if stt == RoomStatus.AVAILABLE else "red" if stt == RoomStatus.OCCUPIED else "orange"
                    c4.markdown(f":{color}[{stt}]")
                    
                    # Actions - Compact buttons
                    with c5:
                        b_edit, b_del = st.columns([1, 1], gap="small")
                        if b_edit.button("✏️", key=f"btn_edit_{r['id']}", help="Sửa thông tin"):
                            st.session_state["edit_room"] = r
                            st.rerun()
                        
                        if b_del.button("🗑️", key=f"btn_del_{r['id']}", help="Xóa phòng này"):
                            delete_room(r['id'])
                            if st.session_state.get("edit_room", {}).get("id") == r['id']:
                                st.session_state["edit_room"] = None
                            st.rerun()
                    st.markdown('<hr style="margin: 2px 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)
            else:
                st.info("Chưa có phòng nào. Hãy thêm ở bên trái.")

# --- TAB 3: HỆ THỐNG & TÀI KHOẢN THANH TOÁN ---
with tab_system:
    # 1. CẤU HÌNH THÔNG TIN ĐƠN VỊ
    st.subheader("🏢 Thông tin đơn vị")
    st.caption("Thông tin này sẽ hiển thị trên Header của trang Booking và trong các mẫu in ấn.")
    
    # Load config with specific key
    sys_conf = get_system_config("general_info") or {}
    
    with st.form("frm_sys_info"):
        c1, c2 = st.columns(2)
        hotel_name = c1.text_input("Tên đơn vị (Khách sạn/Resort)", value=sys_conf.get("hotel_name", get_resort_name()))
        biz_type = c2.selectbox(
            "Loại hình kinh doanh",
            options=["Resort", "Khách sạn", "Homestay", "Villa", "Nhà nghỉ", "Căn hộ dịch vụ"],
            index=["Resort", "Khách sạn", "Homestay", "Villa", "Nhà nghỉ", "Căn hộ dịch vụ"].index(sys_conf.get("business_type", "Resort")) if sys_conf.get("business_type") in ["Resort", "Khách sạn", "Homestay", "Villa", "Nhà nghỉ", "Căn hộ dịch vụ"] else 0
        )
        
        addr = st.text_input("Địa chỉ", value=sys_conf.get("address", ""))
        
        c3, c4, c5 = st.columns(3)
        phone = c3.text_input("Điện thoại", value=sys_conf.get("phone", ""))
        email = c4.text_input("Email", value=sys_conf.get("email", ""))
        website = c5.text_input("Website", value=sys_conf.get("website", ""))
        
        if st.form_submit_button("💾 Lưu thông tin đơn vị", type="primary"):
            new_conf = {
                "hotel_name": hotel_name,
                "business_type": biz_type,
                "address": addr,
                "phone": phone,
                "email": email,
                "website": website,
                # Giữ lại các field cũ nếu có (tránh ghi đè mất data holiday)
                "holidays": sys_conf.get("holidays", []),
                "holiday_notes": sys_conf.get("holiday_notes", {}),
                "weekend_weekdays": sys_conf.get("weekend_weekdays", [5, 6])
            }
            # Lưu vào key 'general_info'
            save_system_config("general_info", new_conf)
            # Clear cache để tên resort cập nhật ngay lập tức
            get_resort_name.clear()
            st.toast("Đã lưu thông tin đơn vị!", icon="🏢")
            st.rerun()

    st.divider()

    # 2. TÀI KHOẢN THANH TOÁN
    st.subheader("💳 Tài khoản thanh toán (Ngân hàng)")
    st.caption(
        "Khai báo thông tin tài khoản để in trên Bill và hiển thị QR khi khách thanh toán online."
    )

    # Lấy cấu hình hiện có
    current_cfg = get_payment_config()

    col_txt, col_qr = st.columns([1.2, 1])

    with col_txt:
        with st.form("frm_payment_config"):
            bank_name = st.text_input(
                "Ngân hàng",
                value=current_cfg.get("bank_name", ""),
                placeholder="VD: Vietcombank",
            )
            bank_id = st.text_input(
                "Mã ngân hàng (VietQR bankId/BIN)",
                value=current_cfg.get("bank_id", ""),
                placeholder="VD: 970436 (Vietcombank)",
            )
            account_name = st.text_input(
                "Tên chủ tài khoản",
                value=current_cfg.get("account_name", ""),
                placeholder="VD: CÔNG TY TNHH ...",
            )
            account_number = st.text_input(
                "Số tài khoản",
                value=current_cfg.get("account_number", ""),
                placeholder="VD: 0123456789",
            )
            note = st.text_area(
                "Ghi chú hiển thị trên Bill (tuỳ chọn)",
                value=current_cfg.get("note", ""),
                placeholder="VD: Nội dung chuyển khoản: Tên + SĐT khách",
            )

            submitted = st.form_submit_button(
                "💾 Lưu thông tin tài khoản", type="primary", use_container_width=True
            )

            if submitted:
                cfg = dict(
                    bank_name=bank_name.strip(),
                    bank_id=bank_id.strip(),
                    account_name=account_name.strip(),
                    account_number=account_number.strip(),
                    note=note.strip(),
                )
                try:
                    save_payment_config(cfg)
                    st.success("Đã lưu thông tin tài khoản thanh toán.")
                except Exception as e:
                    st.error(f"Lỗi khi lưu cấu hình: {e}")

    with col_qr:
        st.markdown("**Xem trước VietQR tự động**")
        st.caption(
            "Hệ thống sẽ tự tạo ảnh VietQR từ Mã ngân hàng (bankId/BIN) và Số tài khoản. Không cần upload ảnh QR."
        )

        cfg = get_payment_config() or {}
        bank_id_cfg = cfg.get("bank_id")
        acc_no_cfg = cfg.get("account_number")

        if bank_id_cfg and acc_no_cfg:
            qr_url = (
                f"https://img.vietqr.io/image/"
                f"{bank_id_cfg}-{acc_no_cfg}-compact2.png?"
                f"accountName={quote_plus(cfg.get('account_name',''))}&"
                f"addInfo={quote_plus(cfg.get('note','Thanh toan tien phong'))}"
            )
            st.image(qr_url, caption="VietQR được tạo tự động", use_column_width=True)
            st.code(qr_url, language="text")
        else:
            st.info(
                "Nhập Mã ngân hàng (VietQR bankId/BIN) và Số tài khoản ở bên trái để tạo QR tự động."
            )

# --- TAB 4: QUẢN LÝ NHÂN VIÊN ---
with tab_staff:
    st.subheader("👥 Quản lý Nhân viên & Phân quyền")
    
    # Check permissions
    current_user = st.session_state.get("user", {})
    if not has_permission(Permission.MANAGE_STAFF):
        st.error("⛔ Bạn không có quyền truy cập khu vực này. Cần quyền 'Quản lý nhân viên'.")
    else:
        col_u_form, col_u_list = st.columns([1, 2], gap="medium")
        
        # --- STATE MANAGEMENT ---
        if "edit_user" not in st.session_state:
            st.session_state["edit_user"] = None
            
        edit_user = st.session_state["edit_user"]
        is_edit_mode = edit_user is not None
        
        # 1. Form Thêm/Sửa User
        with col_u_form:
            with st.container(border=True):
                form_title = f"✏️ Sửa: {edit_user['username']}" if is_edit_mode else "➕ Thêm Nhân viên"
                st.subheader(form_title)
                
                # Default values
                d_name = edit_user.get('full_name', '') if is_edit_mode else ''
                d_email = edit_user.get('username', '') if is_edit_mode else ''
                d_phone = edit_user.get('phone_number', '') if is_edit_mode else ''
                d_role = edit_user.get('role', UserRole.RECEPTIONIST) if is_edit_mode else UserRole.RECEPTIONIST
                d_active = edit_user.get('is_active', True) if is_edit_mode else True
                
                with st.form("frm_user"):
                    u_name = st.text_input("Họ và Tên", value=d_name, placeholder="Nguyễn Văn A")
                    u_email = st.text_input(
                        "Tên đăng nhập (Email)", 
                        value=d_email, 
                        placeholder="user@bamboo.com",
                        disabled=is_edit_mode
                    ).strip()
                    u_phone = st.text_input("Số điện thoại", value=d_phone, placeholder="0901234567")
                    
                    role_options = {
                        UserRole.ADMIN: "Quản trị viên (Admin)",
                        UserRole.MANAGER: "Quản lý (Manager)",
                        UserRole.ACCOUNTANT: "Kế toán (Accountant)",
                        UserRole.RECEPTIONIST: "Lễ tân (Receptionist)"
                    }
                    
                    # RESTRICTION: Non-Admin cannot assign Admin role
                    current_role = current_user.get("role")
                    if current_role != UserRole.ADMIN:
                        if UserRole.ADMIN in role_options:
                            del role_options[UserRole.ADMIN]

                    role_list = list(role_options.keys())
                    try:
                        if isinstance(d_role, str):
                            d_role = UserRole(d_role)
                        role_idx = role_list.index(d_role)
                    except:
                        role_idx = len(role_list) - 1 if role_list else 0
                    
                    u_role = st.selectbox(
                        "Vai trò", 
                        options=role_list, 
                        format_func=lambda x: role_options[x], 
                        index=role_idx
                    )
                    
                    u_active = st.checkbox("Tài khoản hoạt động", value=d_active)
                    
                    if is_edit_mode:
                        u_pass = st.text_input(
                            "Mật khẩu mới", 
                            type="password", 
                            placeholder="Để trống nếu không đổi mật khẩu"
                        )
                    else:
                        u_pass = st.text_input(
                            "Mật khẩu", 
                            type="password", 
                            placeholder="Để trống = Mặc định 123456"
                        )
                    
                    btn_label = "💾 Cập nhật" if is_edit_mode else "➕ Lưu Nhân viên"
                    if st.form_submit_button(btn_label, type="primary"):
                        if not u_email or not u_name:
                            st.error("Vui lòng nhập Tên và Email!")
                        else:
                            if is_edit_mode:
                                from src.db import get_user
                                update_data = {
                                    "full_name": u_name,
                                    "phone_number": u_phone,
                                    "role": u_role.value if hasattr(u_role, 'value') else u_role,
                                    "is_active": u_active
                                }
                                
                                if u_pass:
                                    update_data["password_hash"] = hash_password(u_pass)
                                
                                existing_user = get_user(u_email)
                                if existing_user:
                                    existing_user.update(update_data)
                                    create_user(existing_user)
                                    st.toast(f"✅ Đã cập nhật thông tin {u_name}!", icon="🎉")
                                    st.session_state["edit_user"] = None
                                    st.rerun()
                            else:
                                raw_pass = u_pass if u_pass else "123456"
                                
                                new_user = User(
                                    username=u_email,
                                    password_hash=hash_password(raw_pass),
                                    full_name=u_name,
                                    phone_number=u_phone,
                                    role=u_role,
                                    is_active=u_active
                                )
                                create_user(new_user.to_dict())
                                st.toast(f"✅ Đã thêm nhân viên {u_name}!", icon="🎉")
                                st.rerun()
                
                if is_edit_mode:
                    if st.button("❌ Hủy bỏ", use_container_width=True):
                        st.session_state["edit_user"] = None
                        st.rerun()

        # 2. Danh sách User
        with col_u_list:
            st.subheader("📋 Danh sách Tài khoản")
            users = get_all_users()
            
            if users:
                # Sort by name
                users.sort(key=lambda x: x.get("username", ""))
                
                # Header
                try:
                    # Use columns layout
                    h1, h2, h3, h4, h5 = st.columns([1.5, 2, 1.5, 1, 1.5])
                    h1.markdown("**Username**")
                    h2.markdown("**Họ tên**")
                    h3.markdown("**Vai trò**")
                    h4.markdown("**TT**")
                    h5.markdown("**Thao tác**")
                    st.markdown('<hr style="margin: 5px 0; border-top: 1px solid #ddd;">', unsafe_allow_html=True)
                    
                    for u in users:
                        with st.container():
                            c1, c2, c3, c4, c5 = st.columns([1.5, 2, 1.5, 1, 1.5])
                            c1.write(f"`{u['username']}`")
                            c2.write(u.get('full_name', ''))
                            
                            r = u.get('role', 'receptionist')
                            r_map = {
                                "admin": "👑 Admin",
                                "manager": "👔 Quản lý",
                                "accountant": "💼 Kế toán",
                                "receptionist": "🛎️ Lễ tân"
                            }
                            c3.write(r_map.get(r, r))
                            
                            is_act = u.get('is_active', True)
                            c4.markdown("✅" if is_act else "❌")
                            
                            with c5:
                                b_edit, b_del = st.columns([1, 1], gap="small")
                                
                                # RESTRICTION: Non-Admin cannot edit/delete Admin
                                is_target_admin = (r == "admin" or r == UserRole.ADMIN)
                                can_modify = True
                                if is_target_admin and current_user.get("role") != UserRole.ADMIN:
                                    can_modify = False

                                # Nút sửa với text rõ ràng
                                with b_edit:
                                    if can_modify:
                                        if st.button("✏️ Sửa", key=f"edit_{u['username']}", use_container_width=True):
                                            st.session_state["edit_user"] = u
                                            st.rerun()
                                    else:
                                         st.button("🔒", key=f"lk_e_{u['username']}", disabled=True, use_container_width=True, help="Chỉ Admin mới được sửa tài khoản Admin")
                                    
                                with b_del:
                                    if can_modify:
                                        if st.button("🗑️ Xóa", key=f"del_{u['username']}", use_container_width=True):
                                            if u['username'] == current_user.get("username"):
                                                st.toast("Không thể tự xóa chính mình!", icon="⚠️")
                                            else:
                                                delete_user(u['username'])
                                                if edit_user and edit_user['username'] == u['username']:
                                                    st.session_state["edit_user"] = None
                                                st.rerun()
                                    else:
                                         st.button("🔒", key=f"lk_d_{u['username']}", disabled=True, use_container_width=True)
                            st.markdown('<hr style="margin: 2px 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Lỗi hiển thị danh sách: {e}")
            else:
                st.info("Chưa có nhân viên nào. Hãy thêm ở cột bên trái.")

# --- TAB 6: QUẢN LÝ PHÂN QUYỀN ---
with tab_permissions:
    st.subheader("🔐 Quản lý Phân quyền Chi tiết")
    
    # Check permissions - Chỉ Admin mới được quản lý phân quyền
    if not has_permission(Permission.MANAGE_PERMISSIONS):
        st.error("⛔ Bạn không có quyền truy cập khu vực này. Cần quyền 'Quản lý phân quyền'.")
    else:
        # Khởi tạo phân quyền mặc định nếu chưa có
        init_default_permissions()
        
        st.info("""
        **Hướng dẫn:** Chọn vai trò bên dưới, sau đó tick ✅ vào các quyền mà vai trò đó được phép sử dụng.
        Admin luôn có tất cả quyền và không thể thay đổi.
        """)
        
        # Dropdown chọn vai trò
        role_options = {
            UserRole.ADMIN: "👑 Quản trị viên (Admin)",
            UserRole.MANAGER: "👔 Quản lý (Manager)",
            UserRole.ACCOUNTANT: "💼 Kế toán (Accountant)",
            UserRole.RECEPTIONIST: "🛎️ Lễ tân (Receptionist)"
        }
        
        selected_role = st.selectbox(
            "Chọn vai trò để cấu hình:",
            options=list(role_options.keys()),
            format_func=lambda x: role_options[x],
            index=1  # Default: Manager
        )
        
        # Lấy cấu hình hiện tại
        all_perms = get_all_role_permissions()
        current_perms = set(all_perms.get(selected_role.value, []))
        
        # Admin không thể thay đổi
        if selected_role == UserRole.ADMIN:
            st.warning("⚠️ Admin luôn có toàn bộ quyền. Không thể thay đổi cấu hình.")
            
            # Hiển thị danh sách quyền của Admin (read-only)
            st.markdown("#### Quyền của Admin:")
            all_permission_values = [p.value for p in Permission]
            
            # Nhóm theo category
            categories = {}
            for perm_enum in Permission:
                meta = PERMISSION_METADATA.get(perm_enum, {})
                cat = meta.get("category", "Khác")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(perm_enum)
            
            for cat_name, perms in categories.items():
                icon = PERMISSION_METADATA.get(perms[0], {}).get("icon", "")
                st.markdown(f"##### {icon} {cat_name}")
                for perm in perms:
                    meta = PERMISSION_METADATA.get(perm, {})
                    name = meta.get("name", perm.value)
                    st.markdown(f"✅ {name}")
        
        else:
            # Form để cấu hình quyền
            with st.form(f"frm_permissions_{selected_role.value}"):
                st.markdown(f"### Cấu hình quyền cho: {role_options[selected_role]}")
                
                # Tạo dict để lưu trạng thái checkbox
                new_permissions = set()
                
                # Nhóm quyền theo category
                categories = {}
                for perm_enum in Permission:
                    meta = PERMISSION_METADATA.get(perm_enum, {})
                    cat = meta.get("category", "Khác")
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(perm_enum)
                
                # Render checkbox theo từng category
                for cat_name, perms in categories.items():
                    # Get icon from first permission in category
                    icon = PERMISSION_METADATA.get(perms[0], {}).get("icon", "")
                    st.markdown(f"##### {icon} {cat_name}")
                    
                    # Tạo 2 cột để hiển thị checkbox gọn hơn
                    cols = st.columns(2)
                    for idx, perm in enumerate(perms):
                        meta = PERMISSION_METADATA.get(perm, {})
                        name = meta.get("name", perm.value)
                        
                        # Check xem quyền này có trong cấu hình hiện tại không
                        is_checked = perm.value in current_perms
                        
                        # Hiển thị checkbox
                        col = cols[idx % 2]
                        with col:
                            checked = st.checkbox(
                                name,
                                value=is_checked,
                                key=f"perm_{selected_role.value}_{perm.value}"
                            )
                            
                            if checked:
                                new_permissions.add(perm.value)
                    
                    st.markdown("---")
                
                # Nút lưu
                col_save, col_reset = st.columns([1, 1])
                
                with col_save:
                    submitted = st.form_submit_button("💾 Lưu cấu hình", type="primary", use_container_width=True)
                
                with col_reset:
                    reset = st.form_submit_button("🔄 Reset về mặc định", type="secondary", use_container_width=True)
                
                if submitted:
                    # Lưu cấu hình mới
                    save_role_permissions(selected_role.value, list(new_permissions))
                    st.success(f"✅ Đã lưu cấu hình phân quyền cho {role_options[selected_role]}!")
                    st.rerun()
                
                if reset:
                    # Reset về cấu hình mặc định
                    from src.models import DEFAULT_ROLE_PERMISSIONS
                    default_perms = DEFAULT_ROLE_PERMISSIONS.get(selected_role, [])
                    perm_values = [p.value if hasattr(p, 'value') else p for p in default_perms]
                    save_role_permissions(selected_role.value, perm_values)
                    st.success(f"✅ Đã reset về cấu hình mặc định cho {role_options[selected_role]}!")
                    st.rerun()
        
        # Hiển thị tóm tắt cấu hình hiện tại của tất cả vai trò
        st.divider()
        st.markdown("### 📋 Tổng quan Phân quyền Hiện tại")
        
        summary_data = []
        for role_enum in UserRole:
            role = role_enum.value
            perms = all_perms.get(role, [])
            summary_data.append({
                "Vai trò": role_options.get(role_enum, role),
                "Số quyền": len(perms),
                "Chi tiết": ", ".join([PERMISSION_METADATA.get(Permission(p), {}).get("name", p) for p in perms[:3]]) + ("..." if len(perms) > 3 else "")
            })
        
        import pandas as pd
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
