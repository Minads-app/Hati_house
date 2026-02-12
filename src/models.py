from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from enum import Enum
from datetime import datetime

# --- 1. CẤU HÌNH GIÁ & LOẠI PHÒNG ---

class PriceConfig(BaseModel):
    """
    Cấu hình giá tiền.
    LƯU Ý: hourly_blocks phải dùng key là STRING (Firestore yêu cầu).
    VD: {"1": 50000, "2": 90000} thay vì {1: 50000}
    """
    hourly_blocks: Dict[str, float] = Field(default_factory=dict)
    overnight_price: float = 0.0
    daily_price: float = 0.0
    extra_adult_surcharge: float = 0.0
    extra_adult_surcharge: float = 0.0
    extra_child_surcharge: float = 0.0
    
    # --- Cấu hình cho phép loại hình thuê ---
    enable_hourly: bool = True
    enable_overnight: bool = True
    enable_daily: bool = True

class RoomType(BaseModel):
    type_code: str
    name: str
    default_adults: int = 2
    default_children: int = 0
    default_children: int = 0
    pricing: PriceConfig
    
    # --- Cấu hình giá Lễ/Tết & Cuối tuần ---
    pricing_weekend: Optional[PriceConfig] = None
    pricing_holiday: Optional[PriceConfig] = None

    def to_dict(self):
        try:
            return self.model_dump()
        except AttributeError:
            return self.dict()

# --- 2. QUẢN LÝ PHÒNG (ROOMS) ---

class RoomStatus(str, Enum):
    AVAILABLE = "Trống"      # Màu xanh
    RESERVED = "Đặt trước"   # Màu cam (Mới)
    PENDING_PAYMENT = "Chờ thanh toán"  # Chờ khách chuyển khoản / upload bill
    OCCUPIED = "Đang ở"      # Màu đỏ
    DIRTY = "Chưa dọn"       # Màu vàng
    MAINTENANCE = "Bảo trì"  # Màu xám
    TEMP_LOCKED = "Đang thao tác" # Màu vàng cam (Giữ chỗ tạm thời)

class Room(BaseModel):
    id: str                 # Số phòng: 101, 201
    room_type_code: str     # Link tới RoomType (VD: STD)
    floor: str              # Khu vực / Tầng (VD: Khu A, Tầng 1)
    status: RoomStatus = RoomStatus.AVAILABLE
    note: str = ""
    current_booking_id: Optional[str] = None # Link tới booking đang ở
    
    # --- Fields cho cơ chế giữ phòng (Temporary Hold) ---
    locked_until: Optional[datetime] = None  # Thời điểm hết hạn giữ phòng
    locked_by: Optional[str] = None          # ID phiên làm việc (Session ID) của người đang giữ

    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()

# --- 3. QUẢN LÝ ĐẶT PHÒNG (BOOKING) ---

class BookingType(str, Enum):
    HOURLY = "Theo giờ"
    OVERNIGHT = "Qua đêm"
    DAILY = "Theo ngày"

class BookingStatus(str, Enum):
    CONFIRMED = "Đã đặt"     # Khách đặt trước, chưa đến
    CHECKED_IN = "Đang ở"    # Khách đang ở
    COMPLETED = "Hoàn tất"   # Đã thanh toán
    CANCELLED = "Hủy"

class Booking(BaseModel):
    id: Optional[str] = None
    room_id: str
    customer_name: str
    customer_phone: str = ""
    customer_type: str = "Khách lẻ"
    booking_type: BookingType
    
    status: BookingStatus = BookingStatus.CHECKED_IN 
    
    check_in: datetime
    check_out_expected: datetime
    price_original: float = 0.0
    deposit: float = 0.0
    note: str = ""
    
    # Các trường cập nhật khi Check-out
    check_out_actual: Optional[datetime] = None
    total_amount: float = 0.0
    service_fee: float = 0.0  # Phụ thu / Dịch vụ
    payment_method: str = ""

    # --- Trường phục vụ đặt phòng online ---
    is_online: bool = False                           # Booking được tạo từ trang khách tự đặt
    online_payment_type: str = ""                    # "full" hoặc "deposit"
    online_payment_status: str = "pending"           # "pending" / "waiting_confirm" / "confirmed"
    payment_screenshot_b64: Optional[str] = None     # Ảnh chụp màn hình thanh toán (base64)
    payment_screenshot_name: str = ""                # Tên file ảnh
    payment_screenshot_mime: str = ""                # MIME type ảnh

    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()

# --- 4. CẤU HÌNH HỆ THỐNG (SYSTEM CONFIG) ---

from src.config import AppConfig

class SystemConfig(BaseModel):
    hotel_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    business_type: str = "Resort" # Homestay, Khách sạn, Resort...
    
    # Các cấu hình khác (nếu cần sync với model)
    holidays: List[str] = Field(default_factory=list)
    holiday_notes: Dict[str, str] = Field(default_factory=dict)
    
    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()

# --- 5. NGƯỜI DÙNG & PHÂN QUYỀN (AUTH) ---

class UserRole(str, Enum):
    ADMIN = "admin"             # Owner/Admin: Full quyền
    MANAGER = "manager"         # Quản lý: Full quyền trừ Nhân viên & Cấu hình nhạy cảm
    ACCOUNTANT = "accountant"   # Kế toán: Xem báo cáo, không sửa cấu hình
    RECEPTIONIST = "receptionist" # Lễ tân: Check-in/out, không xem báo cáo/settings

class Permission(str, Enum):
    """Danh sách các quyền chi tiết trong hệ thống"""
    # Dashboard
    VIEW_DASHBOARD = "view_dashboard"
    
    # Booking
    VIEW_BOOKING = "view_booking"
    CREATE_BOOKING = "create_booking"
    UPDATE_BOOKING = "update_booking"
    DELETE_BOOKING = "delete_booking"
    CHECKIN_CHECKOUT = "checkin_checkout"
    
    # Finance
    VIEW_FINANCE = "view_finance"
    EXPORT_REPORTS = "export_reports"
    
    # Services
    VIEW_SERVICES = "view_services"
    MANAGE_SERVICES = "manage_services"
    CREATE_SERVICE_ORDER = "create_service_order"
    
    # Settings
    VIEW_SETTINGS = "view_settings"
    MANAGE_ROOM_TYPES = "manage_room_types"
    MANAGE_ROOMS = "manage_rooms"
    MANAGE_STAFF = "manage_staff"
    MANAGE_PERMISSIONS = "manage_permissions"
    MANAGE_SYSTEM_CONFIG = "manage_system_config"

# Cấu hình quyền mặc định cho từng vai trò
DEFAULT_ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        # Admin có TẤT CẢ quyền
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_BOOKING, Permission.CREATE_BOOKING, Permission.UPDATE_BOOKING, 
        Permission.DELETE_BOOKING, Permission.CHECKIN_CHECKOUT,
        Permission.VIEW_FINANCE, Permission.EXPORT_REPORTS,
        Permission.VIEW_SERVICES, Permission.MANAGE_SERVICES, Permission.CREATE_SERVICE_ORDER,
        Permission.VIEW_SETTINGS, Permission.MANAGE_ROOM_TYPES, Permission.MANAGE_ROOMS,
        Permission.MANAGE_STAFF, Permission.MANAGE_PERMISSIONS, Permission.MANAGE_SYSTEM_CONFIG,
    ],
    UserRole.MANAGER: [
        # Manager có hầu hết quyền trừ phân quyền và cấu hình hệ thống
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_BOOKING, Permission.CREATE_BOOKING, Permission.UPDATE_BOOKING,
        Permission.DELETE_BOOKING, Permission.CHECKIN_CHECKOUT,
        Permission.VIEW_FINANCE, Permission.EXPORT_REPORTS,
        Permission.VIEW_SERVICES, Permission.MANAGE_SERVICES, Permission.CREATE_SERVICE_ORDER,
        Permission.VIEW_SETTINGS, Permission.MANAGE_ROOM_TYPES, Permission.MANAGE_ROOMS,
        Permission.MANAGE_STAFF,
    ],
    UserRole.ACCOUNTANT: [
        # Kế toán: Chỉ xem và xuất báo cáo
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_BOOKING,
        Permission.VIEW_FINANCE, Permission.EXPORT_REPORTS,
        Permission.VIEW_SERVICES,
    ],
    UserRole.RECEPTIONIST: [
        # Lễ tân: Đặt phòng và dịch vụ, không xem tài chính
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_BOOKING, Permission.CREATE_BOOKING, Permission.UPDATE_BOOKING,
        Permission.CHECKIN_CHECKOUT,
        Permission.VIEW_SERVICES, Permission.CREATE_SERVICE_ORDER,
    ],
}

# Metadata cho từng quyền (hiển thị trên UI)
PERMISSION_METADATA = {
    # Dashboard
    Permission.VIEW_DASHBOARD: {
        "name": "Xem trang Dashboard",
        "category": "Dashboard",
        "icon": "📊"
    },
    
    # Booking
    Permission.VIEW_BOOKING: {
        "name": "Xem trang Đặt phòng",
        "category": "Đặt phòng",
        "icon": "📅"
    },
    Permission.CREATE_BOOKING: {
        "name": "Tạo đặt phòng mới",
        "category": "Đặt phòng",
        "icon": "📅"
    },
    Permission.UPDATE_BOOKING: {
        "name": "Sửa đặt phòng",
        "category": "Đặt phòng",
        "icon": "📅"
    },
    Permission.DELETE_BOOKING: {
        "name": "Xóa đặt phòng",
        "category": "Đặt phòng",
        "icon": "📅"
    },
    Permission.CHECKIN_CHECKOUT: {
        "name": "Check-in / Check-out",
        "category": "Đặt phòng",
        "icon": "📅"
    },
    
    # Finance
    Permission.VIEW_FINANCE: {
        "name": "Xem trang Tài chính",
        "category": "Tài chính",
        "icon": "💰"
    },
    Permission.EXPORT_REPORTS: {
        "name": "Xuất báo cáo",
        "category": "Tài chính",
        "icon": "💰"
    },
    
    # Services
    Permission.VIEW_SERVICES: {
        "name": "Xem trang Dịch vụ",
        "category": "Dịch vụ",
        "icon": "🍽️"
    },
    Permission.MANAGE_SERVICES: {
        "name": "Quản lý menu dịch vụ",
        "category": "Dịch vụ",
        "icon": "🍽️"
    },
    Permission.CREATE_SERVICE_ORDER: {
        "name": "Tạo order dịch vụ",
        "category": "Dịch vụ",
        "icon": "🍽️"
    },
    
    # Settings
    Permission.VIEW_SETTINGS: {
        "name": "Xem trang Cấu hình",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
    Permission.MANAGE_ROOM_TYPES: {
        "name": "Quản lý loại phòng",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
    Permission.MANAGE_ROOMS: {
        "name": "Quản lý danh sách phòng",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
    Permission.MANAGE_STAFF: {
        "name": "Quản lý nhân viên",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
    Permission.MANAGE_PERMISSIONS: {
        "name": "Quản lý phân quyền",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
    Permission.MANAGE_SYSTEM_CONFIG: {
        "name": "Quản lý cấu hình hệ thống",
        "category": "Cấu hình",
        "icon": "⚙️"
    },
}

class User(BaseModel):
    username: str             # Email hoặc Tên đăng nhập
    password_hash: str        # Mật khẩu đã hash
    full_name: str
    phone_number: str = ""    # Số điện thoại
    role: UserRole = UserRole.RECEPTIONIST
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()

# --- 6. DỊCH VỤ & ĂN UỐNG (SERVICES) ---

class ServiceCategory(str, Enum):
    FOOD = "Đồ ăn"
    DRINK = "Đồ uống"
    OTHER = "Dịch vụ" # Giặt ủi, Spa, Thuê xe...

class ServiceItem(BaseModel):
    id: Optional[str] = None
    name: str
    category: ServiceCategory = ServiceCategory.DRINK
    price: float = 0.0
    unit: str = "cái" # cái, ly, chai, đĩa, kg...
    is_active: bool = True # Còn bán hay không

    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()

class ServiceOrder(BaseModel):
    id: Optional[str] = None
    booking_id: str
    room_id: str # Lưu thêm để query nhanh theo phòng
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Danh sách món order: [{ "id": "...", "name": "...", "price": 50, "qty": 2, "total": 100 }]
    items: List[Dict] = Field(default_factory=list)
    
    total_value: float = 0.0
    note: str = ""
    
    def to_dict(self):
        try: return self.model_dump()
        except AttributeError: return self.dict()