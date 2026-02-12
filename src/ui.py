"""
UI Helper Functions - CSS và styling chung cho toàn bộ app
"""
import streamlit as st
from src.db import authenticate_user, get_all_users, create_user, hash_password, create_user_session, verify_user_session, delete_user_session, get_db
from src.models import User, UserRole
import time
import os
import extra_streamlit_components as stx
from datetime import datetime, timedelta

def get_manager():
    # Use key to ensure uniqueness if needed, but session state cache is better
    # Note: re-initializing CookieManager with same key is usually fine, 
    # but let's try to keep it in a variable if feasible, or just return component.
    # Actually, stx.CookieManager() is a component call. It needs to be in the layout.
    # Calling it multiple times renders multiple iframes.
    # We should stick to one call per run if possible, or simple idempotent call.
    # Best practice with stx is often:
    return stx.CookieManager(key="auth_cookie_manager")

def load_custom_css():
    """Load global CSS from methods"""
    css_file = os.path.join(os.path.dirname(__file__), "styles.css")
    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def init_default_admin():

    """Tạo tài khoản Admin mặc định nếu hệ thống chưa có user nào"""
    # Chỉ chạy 1 lần check
    if "admin_checked" in st.session_state:
        return

    db = get_db()
    # Check emptiness by getting just 1 doc
    docs = db.collection("users").limit(1).stream()
    has_user = any(docs)
    
    if not has_user:
        # Create default admin
        default_admin = User(
            username="admin",
            password_hash=hash_password("123456"),
            full_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True
        )
        create_user(default_admin.to_dict())
        st.toast("⚠️ Đã tạo tài khoản mặc định: admin / 123456", icon="🛡️")
    
    st.session_state["admin_checked"] = True

def login_form(cookie_manager=None):
    """Hiển thị form đăng nhập"""
    load_custom_css()
    
    if cookie_manager is None:
        cookie_manager = get_manager()
    
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="collapsedControl"] {
            display: none;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            background-color: white;
            color: #333;
        }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.image("https://cdn-icons-png.flaticon.com/512/295/295128.png", width=80) 
        st.markdown("<h2 style='text-align: center;'>Đăng Nhập</h2>", unsafe_allow_html=True)
        
        with st.form("login_frm"):
            username = st.text_input("Tên đăng nhập", placeholder="admin")
            password = st.text_input("Mật khẩu", type="password", placeholder="******")
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
            
            if st.form_submit_button("Đăng nhập", type="primary", use_container_width=True):
                user = authenticate_user(username, password)
                if user:
                    st.session_state["user"] = user
                    
                    # Clear retry count
                    if "auth_retry_count" in st.session_state:
                        del st.session_state["auth_retry_count"]
                    
                    # 2. Tạo session token & lưu cookie (7 ngày)
                    token = create_user_session(username)
                    cookie_manager.set("auth_token", token, expires_at=datetime.now() + timedelta(days=7))
                    
                    st.success(f"Chào mừng {user.get('full_name')}!")
                    # Increase sleep to ensure cookie is set on frontend before rerun
                    time.sleep(1.0) 
                    st.rerun()
                else:
                    st.error(f"Sai tên đăng nhập hoặc mật khẩu! ({username})")

def require_login():


    """
    Hàm bắt buộc đăng nhập. Đặt ở đầu mỗi trang.
    Nếu chưa login -> Hiện form login -> Chặn render nội dung bằng st.stop()
    Nếu đã login -> Hiển thị nút Logout ở sidebar.
    """
    init_default_admin()
    
    # 0. Init Cookie Manager
    cookie_manager = get_manager()
    
    # If we are logged in, clear retry count to keep state clean
    if "user" in st.session_state:
        if "auth_retry_count" in st.session_state:
             del st.session_state["auth_retry_count"]
    
    # 1. Check if already logged in session
    if "user" not in st.session_state:
        # 2. Try to get cookie
        auth_token = cookie_manager.get(cookie="auth_token")
        
        if auth_token:
            user = verify_user_session(auth_token)
            if user:
                # 1. Update session state
                st.session_state["user"] = user
                st.rerun() # Reload để áp dụng state
        
        # 3. Retry mechanism (Fix Flicker on Cloud)
        # Cookie manager check might be slow on Cloud (async). 
        # We try to wait/rerun a few times before deciding user is NOT logged in.
        if "auth_retry_count" not in st.session_state:
            st.session_state["auth_retry_count"] = 0
            
        if st.session_state["auth_retry_count"] < 5: # Increase retries to 5
            st.session_state["auth_retry_count"] += 1
            # Wait varying time to allow frontend to sync
            time.sleep(0.5) # Increase wait time
            st.rerun()
            
        # 4. Exhausted retries -> Show Login Form
        login_form(cookie_manager)
        st.stop() # Dừng render nội dung bên dưới
    
    # Nếu đã login, hiển thị thông tin user ở sidebar
    user = st.session_state["user"]
    with st.sidebar:
        # Compact User Profile
        st.markdown(f"""
        <div style="margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.2);">
            <div style="font-size: 14px; font-weight: bold;">👤 {user.get('full_name', 'User')}</div>
            <div style="font-size: 14px; opacity: 0.8;">Vai trò: {user.get('role', 'staff')}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Đăng xuất", type="secondary", key="btn_logout"):
            # Clear DB Session
            delete_user_session(user.get("username"))
            # Clear Cookie
            cookie_manager.delete("auth_token")
            # Clear Session State
            st.session_state.pop("user")
            st.session_state.pop("auth_retry_count", None)
            st.rerun()

def apply_sidebar_style():
    """
    Áp dụng CSS tùy chỉnh cho sidebar (left menu) trên tất cả các trang.
    Gọi hàm này ở đầu mỗi trang để đảm bảo sidebar có cùng style.
    """
    load_custom_css()
    
    st.markdown("""
    <style>
        /* Thay đổi màu nền của sidebar */
        [data-testid="stSidebar"] {
            background-color: #3A6F43; /* Màu xanh đậm */
            background-image: linear-gradient(180deg, #3A6F43 0%, #064232 100%);
        }

        /* Chỉnh vị trí nút đóng/mở sidebar (X / >) */
        [data-testid="collapsedControl"] {
            top: 3rem !important;
            display: block !important;
            z-index: 999999 !important;
        }
        
        /* Chỉnh vị trí nút đóng/mở sidebar (X / >) */
        [data-testid="collapsedControl"] {
            top: 3rem !important;
            display: block !important;
            z-index: 999999 !important;
            position: fixed !important;
            left: 1rem !important;
        }
        
        /* Chỉnh vị trí nút X (đóng sidebar) 
           Sử dụng :not([kind="secondary"]) để tránh ảnh hưởng đến các nút menu khác
           Dùng position: absolute để không làm vỡ layout
        */
        [data-testid="stSidebar"] button:not([kind="secondary"]) {
             position: absolute !important;
             top: 2rem !important;
             right: 1rem !important;
             margin-top: 1rem !important;
             z-index: 999999 !important;
             border: none !important;
             background-color: transparent !important;
        }
        
        /* Thay đổi màu chữ trong sidebar */
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }
        
        /* Style cho các nút trong sidebar */
        [data-testid="stSidebar"] button {
            color: #ffffff !important;
        }
        
        /* Style cho các link trong sidebar */
        [data-testid="stSidebar"] a {
            color: #ffffff !important;
        }
        
        /* Style cho header sidebar */
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #ffffff !important;
            margin-bottom: 0px !important; /* Giảm margin dưới header */
            padding-bottom: 0px !important;
        }

        /* --- TỐI ƯU KHOẢNG TRỐNG SIDEBAR --- */
        /* Giảm padding phía trên cùng của sidebar */
        section[data-testid="stSidebar"] > div {
            margin-top: -2rem;
            padding-top: 0rem; /* Giảm từ 2rem -> 1rem */
        }
        
        /* Ẩn nút X tắt sidebar trên mobile nếu không cần thiết, hoặc chỉnh lại */
        
        /* Ẩn menu mặc định của Streamlit */
        [data-testid="stSidebarNav"] {
            display: none !important;
        }
        
        /* Style cho custom menu buttons */
        [data-testid="stSidebar"] button[kind="secondary"] {
            background-color: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: #ffffff !important;
            transition: all 0.3s ease;
            margin-bottom: 2px !important; /* Giảm margin dưới */
            width: 100% !important;
            padding-top: 2px !important; /* Giảm padding nút tối đa */
            padding-bottom: 2px !important;
            border-radius: 4px !important;
            font-size: 13px !important; /* Giảm fontsize */
            min-height: 2.2rem !important; /* Giảm chiều cao nút */
            height: 2.2rem !important;
        }
        
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background-color: rgba(255, 255, 255, 0.25) !important;
            border-color: rgba(255, 255, 255, 0.4) !important;
            transform: translateX(2px);
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"]:hover {
            background-color: transparent !important;
        }
        
        [data-testid="stSidebar"] .stButton {
            margin-bottom: 2px !important;
        }

        [data-testid="stSidebar"] .menu-active-item {
            background-color: rgba(255, 255, 255, 0.22);
            padding: 5px 10px;
            border-radius: 4px;
            margin-bottom: 2px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.3);
            font-size: 13px;
            font-weight: bold;
        }
        
        /* --- TỐI ƯU KHOẢNG TRỐNG MAIN PAGE --- */
        /* Giảm padding top của block container chính */
        .block-container {
            margin-top: -2rem;
            padding-top: 1rem !important; /* Giảm từ 2rem -> 1rem */
            padding-bottom: 1rem !important;
            max-width: 95% !important; /* Tăng chiều rộng nội dung */
        }
        
        /* Giảm khoảng cách giữa các element */
        .element-container {
            margin-bottom: 0.1rem !important; /* Giảm từ 0.5rem -> 0.3rem */
        }
        
        /* Header h1 gọn hơn */
        h1 {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            font-size: 1.8rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        h2 {
            padding-top: 0.5rem !important;
            padding-bottom: 0.2rem !important;
            margin-bottom: 0.2rem !important;
        }
        
        h3 {
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
            margin-bottom: 0rem !important;
        }
        
        /* Giảm padding của metric */
        [data-testid="stMetric"] {
            padding: 0px !important;
        }

        /* Divider gọn hơn */
        hr {
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* --- FIX TOOLTIP BỊ CHE KHUẤT (COMPREHENSIVE) --- */
        /* Remove overflow hidden from all containers */
        div[data-testid="column"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlock"],
        .element-container,
        .stButton {
            overflow: visible !important;
        }
        
        /* Ensure tooltip has highest z-index and proper positioning */
        [role="tooltip"],
        .stTooltipContent,
        [data-testid="stTooltipIcon"],
        [data-baseweb="tooltip"] {
            z-index: 2147483647 !important; /* Max z-index */
            position: fixed !important;
        }
        
        /* Button container must be relative and allow overflow */
        button[title] {
            position: relative !important;
            overflow: visible !important;
        }
        
        /* On hover, increase z-index of button */
        button[title]:hover {
            z-index: 2147483646 !important;
            position: relative !important;
        }
        
        /* Fix for BaseWeb tooltip components */
        [data-baseweb="popover"] {
            z-index: 2147483647 !important;
        }
        
        /* Ensure parent containers don't clip */
        .row-widget.stButton,
        div[data-testid="column"] > div {
            overflow: visible !important;
            position: relative !important;
        }
        
    </style>
    """, unsafe_allow_html=True)

def create_custom_sidebar_menu():
    """
    Tạo custom sidebar menu với tên tùy chỉnh.
    Gọi hàm này trong main.py hoặc các trang để hiển thị menu tùy chỉnh.
    """
    import os
    
    # Detect trang hiện tại (Giữ nguyên logic cũ)
    try:
        import inspect
        frame = inspect.currentframe()
        caller_file = frame.f_back.f_globals.get('__file__', '')
        if 'main.py' in caller_file or caller_file.endswith('main.py'):
            current_page = "main"
        elif '1_Dashboard' in caller_file:
            current_page = "dashboard"
        elif '2_Booking' in caller_file:
            current_page = "booking"
        elif '3_Checkout' in caller_file:
            current_page = "checkout"
        elif '3_Finance' in caller_file:
            current_page = "finance"
        elif '9_Settings' in caller_file:
            current_page = "settings"
        else:
            current_page = "main"
    except:
        current_page = st.session_state.get("current_page", "main")
    
    with st.sidebar:
        # Tiêu đề Menu gọn hơn
        st.markdown("""
        <div style="margin-top: 10px; margin-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 2px;">
            <b style="font-size: 14px;">🎋 MENU</b>
        </div>
        """, unsafe_allow_html=True)
        
        # Định nghĩa menu items (Giữ nguyên logic cũ)
        all_menu_items = [
            ("🏠", "Trang chủ", "main", "main.py", None),
            ("🏨", "Sơ đồ phòng", "dashboard", "pages/1_Dashboard.py", None),
            ("🛎️", "Đặt phòng", "booking", "pages/2_Booking.py", None),
            ("🍽️", "Dịch vụ & Ăn uống", "services", "pages/5_Services.py", None),
            ("💸", "Trả phòng", "checkout", "pages/3_Checkout.py", None),
            ("📊", "Báo cáo", "finance", "pages/3_Finance.py", [UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT]),
            ("⚙️", "Cài đặt", "settings", "pages/9_Settings.py", [UserRole.ADMIN, UserRole.MANAGER]), 
        ]
        
        user = st.session_state.get("user")
        user_role = user.get("role") if user else None
        
        for icon, label, page_id, page_path, roles in all_menu_items:
            # Check permission
            if roles and user_role:
                if user_role not in roles:
                    continue # Skip
            
            is_current = (current_page == page_id)
            
            # Highlight trang hiện tại
            if is_current:
                st.markdown(
                    f'<div class="menu-active-item"><strong>{icon} {label}</strong></div>',
                    unsafe_allow_html=True,
                )
            else:
                if st.button(f"{icon} {label}", key=f"menu_{page_id}", use_container_width=True, type="secondary"):
                    try:
                        st.switch_page(page_path)
                    except Exception as e:
                        st.rerun()

# --- PERMISSION HELPERS ---

def has_permission(permission: str) -> bool:
    """
    Kiểm tra xem user hiện tại có quyền cụ thể không.
    
    Args:
        permission: Permission value (string) hoặc Permission enum
    
    Returns:
        True nếu user có quyền, False nếu không
    """
    from src.db import get_role_permissions
    from src.models import UserRole
    
    # Lấy user hiện tại
    user = st.session_state.get("user")
    if not user:
        return False
    
    # Admin luôn có tất cả quyền
    user_role = user.get("role", "")
    if user_role == UserRole.ADMIN.value:
        return True
    
    # Lấy danh sách quyền của role
    permissions = get_role_permissions(user_role)
    
    # Convert permission to string value if it's enum
    perm_value = permission.value if hasattr(permission, 'value') else permission
    
    return perm_value in permissions

def require_permission(permission: str, error_message: str = None):
    """
    Yêu cầu user phải có quyền cụ thể để tiếp tục.
    Nếu không có quyền, hiển thị lỗi và dừng render.
    
    Args:
        permission: Permission value (string) hoặc Permission enum
        error_message: Thông báo lỗi tùy chỉnh (optional)
    """
    if not has_permission(permission):
        if error_message is None:
            error_message = "⛔ Bạn không có quyền truy cập chức năng này."
        st.error(error_message)
        st.stop()

def get_user_permissions() -> list:
    """
    Lấy danh sách tất cả quyền của user hiện tại.
    
    Returns:
        List[str] - danh sách permission values
    """
    from src.db import get_role_permissions
    from src.models import UserRole, Permission
    
    user = st.session_state.get("user")
    if not user:
        return []
    
    user_role = user.get("role", "")
    
    # Admin có tất cả quyền
    if user_role == UserRole.ADMIN.value:
        return [p.value for p in Permission]
    
    return get_role_permissions(user_role)
