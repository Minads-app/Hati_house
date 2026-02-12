import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import streamlit as st
import os
from datetime import datetime, timedelta
from src.models import Booking, BookingStatus, RoomStatus
import uuid
from src.config import AppConfig


# --- 1. KẾT NỐI FIRESTORE (Named App to avoid conflicts) ---

_APP_NAME = "hati_house"  # Unique name for this project

def init_firebase():
    """Khởi tạo Firebase App với tên riêng, tránh xung đột với dự án khác."""
    # Kiểm tra xem app đã tồn tại chưa
    if _APP_NAME in firebase_admin._apps:
        return  # Đã khởi tạo rồi
    
    try:
        # Ưu tiên 1: File key (Local dev / Configured path)
        key_path = AppConfig.get_firebase_key_path()
        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, name=_APP_NAME)
            print(f"✅ Firebase initialized from {key_path}")
        # Ưu tiên 2: Streamlit Secrets (Cloud deployment)
        elif "firebase" in st.secrets:
            # Convert st.secrets to a standard dict to avoid issues
            key_dict = dict(st.secrets["firebase"])
            
            # Handle private_key newlines - support both formats
            if "private_key" in key_dict:
                # Replace literal \\n string with actual newline
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
                
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred, name=_APP_NAME)
            print("✅ Firebase initialized from Streamlit secrets")
        else:
            error_msg = """
            ⚠️ Firebase Configuration Missing!
            
            For Streamlit Cloud:
            1. Go to App Settings > Secrets
            2. Add your Firebase credentials in TOML format
            3. Run 'python generate_secrets.py' locally to get the correct format
            
            For Local Development:
            - Place 'firebase_key.json' in the project root
            """
            st.error(error_msg)
            raise ValueError("Firebase credentials not found")
    except Exception as e:
        error_detail = f"""
        ❌ Firebase Initialization Error
        
        Error: {str(e)}
        
        Common fixes:
        - Check that private_key in secrets uses \\n (not actual newlines)
        - Verify all required fields are present in secrets
        - Ensure Firebase project has Firestore enabled
        """
        st.error(error_detail)
        # Re-raise to prevent app from running with broken DB
        raise

@st.cache_resource
def get_firebase_client():
    """Cache connection to Firestore to prevent re-initializing on every run"""
    init_firebase()
    app = firebase_admin.get_app(_APP_NAME)
    return firestore.client(app)

def get_db():
    """Lấy object kết nối tới DB (Cached)"""
    return get_firebase_client()

# --- RESORT NAME (Dynamic from Firestore) ---
@st.cache_data(ttl=60)
def get_resort_name():
    """
    Lấy tên resort từ Firestore (config_system/general_info.hotel_name).
    Fallback về AppConfig.RESORT_NAME nếu chưa cấu hình.
    Cache 60 giây để tránh query liên tục.
    """
    try:
        db = get_db()
        doc = db.collection("config_system").document("general_info").get()
        if doc.exists:
            name = doc.to_dict().get("hotel_name", "").strip()
            if name:
                return name
    except Exception:
        pass
    return AppConfig.RESORT_NAME

# --- SMART POLLING HELPERS (Counter-based) ---
def trigger_system_update():
    """Tăng bộ đếm thay đổi hệ thống để các client khác biết mà reload."""
    try:
        db = get_db()
        db.collection("config").document("system_status").set({
            "update_counter": firestore.Increment(1)
        }, merge=True)
    except Exception as e:
        print(f"⚠️ Failed to trigger system update: {e}")

def get_system_update_counter():
    """Lấy giá trị bộ đếm cập nhật hệ thống (số nguyên đơn giản)."""
    try:
        db = get_db()
        doc = db.collection("config").document("system_status").get()
        if doc.exists:
            return doc.to_dict().get("update_counter", 0)
    except Exception:
        pass
    return 0

# --- 2. LOGIC XỬ LÝ DỮ LIỆU (CRUD) ---

def save_room_type_to_db(room_type_data: dict):
    """Lưu hoặc cập nhật loại phòng"""
    db = get_db()
    # Dùng type_code làm ID của document
    doc_id = room_type_data.get("type_code")
    if doc_id:
        db.collection("config_room_types").document(doc_id).set(room_type_data)
        # Clear cache when data changes
        get_all_room_types.clear()

@st.cache_data(ttl=3600)
def get_all_room_types():
    """Lấy danh sách tất cả loại phòng (Cached 1h)"""
    db = get_db()
    docs = db.collection("config_room_types").stream()
    return [doc.to_dict() for doc in docs]

def delete_room_type(type_code: str):
    """Xóa loại phòng"""
    db = get_db()
    if type_code:
        db.collection("config_room_types").document(type_code).delete()
        get_all_room_types.clear()

# --- LOGIC PHÒNG (ROOMS) & HOLDING MECHANISM ---

def save_room_to_db(room_data: dict):
    """Lưu phòng (101, 102...)"""
    db = get_db()
    # Dùng số phòng làm ID (VD: '101')
    doc_id = room_data.get("id")
    if doc_id:
        db.collection("rooms").document(doc_id).set(room_data)

def get_all_rooms():
    """
    Lấy danh sách tất cả phòng.
    - Tự động kiểm tra và nhả phòng bị giữ quá hạn (Lazy Release).
    """
    db = get_db()
    docs = db.collection("rooms").stream()
    rooms = []
    
    now = datetime.now()
    batch = db.batch()
    needs_commit = False

    for doc in docs:
        r = doc.to_dict()
        # Kiểm tra Lazy Release cho TEMP_LOCKED
        if r.get("status") == RoomStatus.TEMP_LOCKED:
            locked_until = r.get("locked_until")
            # Convert timestamp to datetime if needed
            if locked_until and locked_until.tzinfo:
                locked_until = locked_until.replace(tzinfo=None)
                
            if locked_until and locked_until < now:
                # Đã hết hạn giữ -> Release về AVAILABLE
                ref = db.collection("rooms").document(r["id"])
                batch.update(ref, {
                    "status": RoomStatus.AVAILABLE,
                    "locked_until": firestore.DELETE_FIELD,
                    "locked_by": firestore.DELETE_FIELD
                })
                needs_commit = True
                # Update local data for return
                r["status"] = RoomStatus.AVAILABLE.value
                r.pop("locked_until", None)
                r.pop("locked_by", None)

        rooms.append(r)
    
    if needs_commit:
        try:
            batch.commit()
            print("✅ Auto-released expired rooms.")
        except Exception as e:
            print(f"⚠️ Failed to auto-release rooms: {e}")

    return rooms

def hold_room(room_id: str, user_session_id: str, duration_minutes: int = 5) -> tuple[bool, str]:
    """
    Cố gắng giữ phòng trong `duration_minutes`.
    - Sử dụng Transaction để đảm bảo tính toàn vẹn.
    - Trả về (True, "Success") hoặc (False, "Lỗi...").
    """
    if not room_id: return False, "Missing room_id"
    if not user_session_id: return False, "Missing session_id"

    db = get_db()
    room_ref = db.collection("rooms").document(room_id)

    @firestore.transactional
    def _hold_in_transaction(transaction, ref, uid, duration):
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            return False, "Phòng không tồn tại"
        
        data = snapshot.to_dict()
        status = data.get("status")
        current_lock_owner = data.get("locked_by")
        
        now = datetime.now()
        
        # Case 1: Phòng đang AVAILABLE -> Lock được
        if status == RoomStatus.AVAILABLE or status == "Trống":
            pass # OK to lock
            
        # Case 2: Phòng đang TEMP_LOCKED
        elif status == RoomStatus.TEMP_LOCKED or status == "Đang thao tác":
            # Nếu là chính mình đang lock -> Gia hạn
            if current_lock_owner == uid:
                pass # OK to extend
            else:
                # Nếu người khác lock, kiểm tra hết hạn chưa
                locked_until = data.get("locked_until")
                if locked_until:
                    if locked_until.tzinfo: locked_until = locked_until.replace(tzinfo=None)
                    
                    if locked_until > now:
                        return False, "Phòng đang được người khác giữ"
                # Nếu hết hạn -> Cướp lock (OK)
                
        # Case 3: Phòng đang Bận (Occupied, Reserved, Dirty...)
        else:
            return False, f"Phòng đang bận ({status})"

        # Thực hiện Lock
        expire_time = now + timedelta(minutes=duration)
        transaction.update(ref, {
            "status": RoomStatus.TEMP_LOCKED.value,
            "locked_until": expire_time,
            "locked_by": uid
        })
        return True, "Giữ phòng thành công"

    try:
        transaction = db.transaction()
        success, msg = _hold_in_transaction(transaction, room_ref, user_session_id, duration_minutes)
        if success:
            trigger_system_update()
        return success, msg
    except Exception as e:
        return False, str(e)

def release_room_hold(room_id: str, user_session_id: str):
    """
    Nhả phòng (Huỷ giữ) nếu đang được giữ bởi user này.
    """
    if not room_id or not user_session_id: return
    
    db = get_db()
    room_ref = db.collection("rooms").document(room_id)
    
    try:
        doc = room_ref.get()
        if doc.exists:
            data = doc.to_dict()
            # Chỉ nhả nếu đang LOCKED và đúng chủ
            if (data.get("status") == RoomStatus.TEMP_LOCKED and 
                data.get("locked_by") == user_session_id):
                
                room_ref.update({
                    "status": RoomStatus.AVAILABLE.value,
                    "locked_until": firestore.DELETE_FIELD,
                    "locked_by": firestore.DELETE_FIELD
                })
                trigger_system_update()
                return True
    except Exception as e:
        print(f"Error releasing room: {e}")
    return False

def delete_room(room_id: str):
    """Xóa phòng"""
    db = get_db()
    if room_id:
        db.collection("rooms").document(room_id).delete()
# --- LOGIC BOOKING (CHECK-IN) ---

def create_booking(booking: Booking, is_checkin_now: bool):
    """
    Tạo booking mới.
    - Nếu is_checkin_now = True: Phòng -> OCCUPIED (Đang ở)
    - Nếu is_checkin_now = False: Phòng -> RESERVED (Đặt trước)
    """
    db = get_db()
    
    if not booking.id:
        booking.id = str(uuid.uuid4())[:8]
    
    # Xác định trạng thái
    if is_checkin_now:
        booking.status = BookingStatus.CHECKED_IN
        room_status = RoomStatus.OCCUPIED.value
    else:
        booking.status = BookingStatus.CONFIRMED
        # Nếu là booking online, phòng trước tiên ở trạng thái CHỜ THANH TOÁN
        if getattr(booking, "is_online", False):
            room_status = RoomStatus.PENDING_PAYMENT.value
        else:
            room_status = RoomStatus.RESERVED.value

    booking_data = booking.to_dict()
    
    try:
        # 1. Lưu Booking
        db.collection("bookings").document(booking.id).set(booking_data)
        
        # 2. Update trạng thái phòng
        db.collection("rooms").document(booking.room_id).update({
            "status": room_status,
            "current_booking_id": booking.id
        })
        trigger_system_update()
        return True, booking.id
    except Exception as e:
        return False, str(e)

def get_active_booking(room_id: str):
    """Lấy booking đang active của phòng này (nếu có)"""
    db = get_db()
    # Query: tìm booking có room_id == room_id và status == active
    docs = db.collection("bookings")\
        .where(filter=FieldFilter("room_id", "==", room_id))\
        .where(filter=FieldFilter("status", "==", "active"))\
        .limit(1).stream()
    
    for doc in docs:
        return doc.to_dict()
    return None

def cancel_booking(booking_id: str):
    """Hủy booking"""
    db = get_db()
    if booking_id:
        db.collection("bookings").document(booking_id).update({
            "status": "cancelled"
        })
        return True
    return False
# ... (Giữ nguyên code cũ) ...

# --- LOGIC CHECK-OUT ---

def get_occupied_rooms():
    """Lấy danh sách các phòng đang có khách (Occupied)"""
    db = get_db()
    docs = db.collection("rooms").where(filter=FieldFilter("status", "==", "Đang ở")).stream()
    return [doc.to_dict() for doc in docs]

def get_booking_by_id(booking_id: str):
    """Lấy thông tin chi tiết booking"""
    db = get_db()
    doc = db.collection("bookings").document(booking_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def process_checkout(booking_id: str, room_id: str, final_amount: float, payment_method: str, note: str, service_fee: float = 0.0):
    """
    Xử lý trả phòng:
    1. Update Booking: status='Completed', set actual_check_out, final_amount, service_fee
    2. Update Room: status='Chưa dọn' (DIRTY) - cần dọn mới bán được tiếp
    """
    db = get_db()
    try:
        # Tự động tính lại tổng tiền dịch vụ (Service Orders) nếu có
        # Lưu ý: final_amount truyền vào có thể đã bao gồm service_fee nếu UI tính rồi.
        # Nhưng để chắc chắn, ta có thể lưu riêng field 'order_service_total' vào booking.
        
        # Ở đây ta giả định final_amount là TỔNG CỘNG (nguyên tiền phòng + dịch vụ).
        # Nhưng ta nên lưu thêm thông tin service_fee (phụ thu) và order_service_total (tiền gọi món).
        
        total_service_orders = calculate_service_total(booking_id)
        
        # Update Booking
        db.collection("bookings").document(booking_id).update({
            "status": "Completed",
            "check_out_actual": datetime.now(),
            "total_amount": final_amount, 
            "service_fee": service_fee, # Phụ thu khác
            "order_service_total": total_service_orders, # Tiền gọi món
            "payment_method": payment_method,
            "note": note
        })
        
        # Update Room
        db.collection("rooms").document(room_id).update({
            "status": RoomStatus.DIRTY, # Chuyển sang dơ để dọn dẹp
            "current_booking_id": firestore.DELETE_FIELD # Xóa link booking
        })
        trigger_system_update()
        return True, "Thanh toán thành công"
    except Exception as e:
        return False, str(e)

def update_room_status(room_id: str, new_status: str):
    """Hàm phụ trợ: Dùng để cập nhật trạng thái phòng (VD: Dọn xong -> Trống)"""
    db = get_db()
    db.collection("rooms").document(room_id).update({"status": new_status})
    trigger_system_update()

def check_in_reserved_room(room_id: str):
    """
    Check-in nhanh cho phòng đang ở trạng thái Đặt trước.

    - Update booking.status -> "Đang ở"
    - Lưu lại check_in cũ vào `check_in_reserved` (nếu có) và set check_in = now
    - Update room.status -> "Đang ở"
    """
    db = get_db()
    try:
        room_doc = db.collection("rooms").document(room_id).get()
        if not room_doc.exists:
            return False, "Không tìm thấy phòng"

        room = room_doc.to_dict() or {}
        booking_id = room.get("current_booking_id")
        if not booking_id:
            return False, "Phòng đặt trước nhưng thiếu current_booking_id"

        bk_ref = db.collection("bookings").document(booking_id)
        bk_doc = bk_ref.get()
        if not bk_doc.exists:
            return False, "Không tìm thấy booking của phòng"

        bk = bk_doc.to_dict() or {}
        now = datetime.now()

        updates = {
            "status": RoomStatus.OCCUPIED,  # "Đang ở"
            "check_in": now,
        }
        # Lưu lại giờ check-in dự kiến (để truy vết)
        if bk.get("check_in") is not None and bk.get("check_in_reserved") is None:
            updates["check_in_reserved"] = bk.get("check_in")

        bk_ref.update(updates)

        db.collection("rooms").document(room_id).update({
            "status": RoomStatus.OCCUPIED,
        })
        trigger_system_update()

        return True, booking_id
    except Exception as e:
        return False, str(e)

# --- FINANCE / REPORTING ---

def get_all_bookings():
    """Lấy toàn bộ bookings (CẢNH BÁO: CHỈ DÙNG KHI CẦN THIẾT HOẶC DATA ÍT)."""
    db = get_db()
    docs = db.collection("bookings").stream()
    return [doc.to_dict() for doc in docs]

def get_pending_online_bookings():
    """
    Lấy danh sách booking online đang chờ xác nhận thanh toán.
    Filter directly in Firestore.
    """
    db = get_db()
    # status = "pending" (chưa up ảnh) hoặc "waiting_confirm" (đã up ảnh)
    # Lưu ý: Cần composite index nếu field 'is_online' và 'online_payment_status' không có.
    # Tuy nhiên query equality + IN thường được support tốt.
    try:
        docs = db.collection("bookings")\
            .where(filter=FieldFilter("is_online", "==", True))\
            .where(filter=FieldFilter("online_payment_status", "in", ["pending", "waiting_confirm"]))\
            .stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"⚠️ Query pending bookings failed (Index missing?): {e}")
        # Fallback: load all online (ít hơn load all bookings) rồi filter
        docs = db.collection("bookings").where(filter=FieldFilter("is_online", "==", True)).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("online_payment_status") in ["pending", "waiting_confirm"]:
                results.append(data)
        return results

def get_confirmed_online_bookings(limit: int = 20):
    """
    Lấy danh sách booking online đã được xác nhận.
    Sorted by check_in desc, limit 20.
    """
    db = get_db()
    try:
        docs = db.collection("bookings")\
            .where(filter=FieldFilter("is_online", "==", True))\
            .where(filter=FieldFilter("online_payment_status", "==", "confirmed"))\
            .order_by("check_in", direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"⚠️ Query confirmed bookings failed (Index missing?): {e}")
        # Fallback manual
        docs = db.collection("bookings").where(filter=FieldFilter("is_online", "==", True)).stream()
        all_items = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("online_payment_status") == "confirmed":
                all_items.append(data)
        
        all_items.sort(key=lambda x: x.get("check_in") or datetime.min, reverse=True)
        return all_items[:limit]

# ... existing update_online_payment_proof ...

# ... existing confirm_online_booking ...

# ... existing get_payment_config ...

# ... existing save_payment_config ...

# ... existing get_active_bookings_dict ...

# ... existing get_system_config ...

# ... existing save_system_config ...

def get_completed_bookings(start_dt: datetime | None = None, end_dt: datetime | None = None):
    """
    Lấy danh sách booking đã hoàn tất (có check_out_actual) trong khoảng thời gian.
    Queries Firestore directly using 'check_out_actual' field.
    """
    db = get_db()
    
    # Query base
    query = db.collection("bookings")
    
    # Filter range
    # Note: Firestore timestamps are UTC/Offset-aware. 
    # Ensure start_dt/end_dt are handled correctly.
    if start_dt:
        query = query.where(filter=FieldFilter("check_out_actual", ">=", start_dt))
    if end_dt:
        query = query.where(filter=FieldFilter("check_out_actual", "<=", end_dt))
        
    try:
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"⚠️ Query completed bookings failed (Index or Field missing?): {e}")
        # Nếu fail (VD chưa đánh index), fallback về logic cũ (slow but safe)
        all_bk = get_all_bookings()
        results = []
        for b in all_bk:
            ts = b.get("check_out_actual")
            if not ts: continue
            if ts.tzinfo: ts = ts.replace(tzinfo=None)
            
            s = start_dt.replace(tzinfo=None) if start_dt and start_dt.tzinfo else start_dt
            e = end_dt.replace(tzinfo=None) if end_dt and end_dt.tzinfo else end_dt
            
            if s and ts < s: continue
            if e and ts > e: continue
            results.append(b)
        return results

def update_online_payment_proof(
    booking_id: str,
    screenshot_b64: str,
    filename: str,
    mime: str,
):
    """Lưu ảnh chụp thanh toán cho booking online và chuyển trạng thái sang 'waiting_confirm'."""
    db = get_db()
    db.collection("bookings").document(booking_id).update(
        {
            "payment_screenshot_b64": screenshot_b64,
            "payment_screenshot_name": filename,
            "payment_screenshot_mime": mime,
            "online_payment_status": "waiting_confirm",
        }
    )

def confirm_online_booking(booking_id: str):
    """Nhân viên lễ tân xác nhận đã nhận tiền đặt cọc / thanh toán.

    - Cập nhật online_payment_status = 'confirmed'
    - Chuyển trạng thái phòng từ 'Chờ thanh toán' -> 'Đặt trước'
    """
    db = get_db()
    try:
        bk_ref = db.collection("bookings").document(booking_id)
        bk_doc = bk_ref.get()
        if not bk_doc.exists:
            return False, "Không tìm thấy booking"

        data = bk_doc.to_dict() or {}
        room_id = data.get("room_id")

        # 1. Cập nhật trạng thái thanh toán online
        bk_ref.update({"online_payment_status": "confirmed"})

        # 2. Chuyển trạng thái phòng sang Đặt trước
        if room_id:
            db.collection("rooms").document(room_id).update(
                {"status": RoomStatus.RESERVED.value}
            )

        trigger_system_update()
        return True, "OK"
    except Exception as e:
        return False, str(e)

# --- SYSTEM CONFIG (PAYMENT INFO) ---

def get_payment_config():
    """
    Lấy cấu hình tài khoản thanh toán (ngân hàng) dùng chung cho:
    - Bill checkout tại quầy
    - Đặt phòng online (QR thanh toán)

    Lưu tại: collection 'config_system', document 'payment'.
    """
    db = get_db()
    doc = db.collection("config_system").document("payment").get()
    if doc.exists:
        return doc.to_dict()
    return {}

def save_payment_config(config: dict):
    """Lưu cấu hình tài khoản thanh toán."""
    db = get_db()
    db.collection("config_system").document("payment").set(config or {})

def get_active_bookings_dict():
    """
    Lấy toàn bộ booking đang hoạt động (Occupied, Reserved, Checked_in)
    Trả về dict: { booking_id: booking_data }
    Giúp tránh lỗi N+1 query khi hiển thị danh sách phòng.
    """
    db = get_db()
    # Statuses that imply "active"
    # Note: Querying with 'in' operator is supported in Firestore
    statuses = [
        BookingStatus.CONFIRMED.value,
        BookingStatus.CHECKED_IN.value,
        "Confirmed", 
        "CheckedIn",
        # RoomStatus values might be mixed in booking status in legacy data?
        # Booking status is usually CONFIRMED or CHECKED_IN or COMPLETED.
        # Room status is OCCUPIED/RESERVED.
        # We need bookings where status is NOT Completed/Cancelled.
    ]
    
    # Better approach: Query all bookings that are NOT Completed/Cancelled?
    # Or query by Room Status?
    # Actually, we rely on room.current_booking_id. 
    # So we can just fetch ALL active bookings.
    
    docs = db.collection("bookings").where(filter=FieldFilter("status", "in", statuses)).stream()
    return {doc.id: doc.to_dict() for doc in docs}

@st.cache_data(ttl=300) # Cache 5 mins
def get_system_config(key: str):
    """Lấy cấu hình hệ thống theo key (VD: 'special_days')"""
    db = get_db()
    doc = db.collection("config_system").document(key).get()
    if doc.exists:
        return doc.to_dict()
    return {}

def save_system_config(key: str, config: dict):
    """Lưu cấu hình hệ thống theo key"""
    db = get_db()
    db.collection("config_system").document(key).set(config or {})

def get_completed_bookings(start_dt: datetime | None = None, end_dt: datetime | None = None):
    """
    Lấy danh sách booking đã hoàn tất trong khoảng thời gian.

    Ghi chú: Do dữ liệu trạng thái đang có thể lệch chuẩn ("Completed"/"Hoàn tất"/Enum),
    hàm này sẽ lọc mềm và ưu tiên theo `check_out_actual`.
    """
    bookings = get_all_bookings()

    completed_statuses = {
        "Completed",
        "Hoàn tất",
        getattr(BookingStatus, "COMPLETED", None),
    }
    # Loại bỏ None/Enum objects, convert sang string nếu cần
    completed_statuses = set([s.value if hasattr(s, "value") else s for s in completed_statuses if s])

    def _in_range(ts: datetime | None) -> bool:
        if ts is None:
            return False
        # Firestore đôi khi trả datetime có tzinfo -> bỏ tzinfo để so sánh ổn định
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        if start_dt:
            s = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
            if ts < s:
                return False
        if end_dt:
            e = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt
            if ts > e:
                return False
        return True

    results = []
    for b in bookings:
        status = b.get("status")
        if hasattr(status, "value"):
            status = status.value
            
        # Ưu tiên booking có check_out_actual, vì đó là phát sinh doanh thu thực
        ts = b.get("check_out_actual")
        
        if ts:
            # Nếu có dữ liệu ngày tháng, chỉ lấy nếu NẰM TRONG khoảng thời gian
            if _in_range(ts):
                results.append(b)
            # Nếu có ts nhưng không khớp range -> Bỏ qua luôn, không check status nữa
            continue

        # Fallback: Chỉ check status nếu KHÔNG CÓ check_out_actual (data cũ/lỗi)
        if status in completed_statuses:
            # Nếu thiếu timestamp thì vẫn trả về (trang Finance sẽ loại/hiển thị cảnh báo)
            results.append(b)

    return results

def get_bookings_for_today():
    """Lấy danh sách booking có check-in hôm nay (Tối ưu query)"""
    db = get_db()
    today = datetime.now().date()
    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())
    
    # Query theo khoảng thời gian check_in
    docs = db.collection("bookings").where(filter=FieldFilter("check_in", ">=", start_dt)).where(filter=FieldFilter("check_in", "<=", end_dt)).stream()
    return [doc.to_dict() for doc in docs]

# --- USER MANAGEMENT & AUTH ---

import hashlib

def hash_password(password: str) -> str:
    """Hash mật khẩu bằng SHA256 (đơn giản, có thể nâng cấp thêm salt)"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(username: str):
    """Lấy thông tin user theo username (email)"""
    # Fix: Kiểm tra username rỗng hoặc chỉ chứa khoảng trắng để tránh lỗi Firestore InvalidArgument
    if not username or not username.strip():
        return None
    db = get_db()
    doc = db.collection("users").document(username).get()
    if doc.exists:
        return doc.to_dict()
    return None

def find_customer_by_phone(phone: str):
    """Tìm thông tin khách hàng gần nhất theo số điện thoại"""
    if not phone or len(phone.strip()) < 3:
        return None
    
    db = get_db()
    # Tìm trong collection bookings, order by check_in desc, limit 1
    # Lưu ý: Cần composite index nếu sort và filter cùng lúc.
    # Để tránh lỗi index, ta có thể filter trước rồi sort in-memory nếu số lượng ít,
    # hoặc chỉ cần lấy 1 document bất kỳ (nếu chấp nhận không phải mới nhất).
    # Tuy nhiên, ta muốn lấy tên mới nhất.
    # Hãy thử query simple equality trước.
    
    docs = db.collection("bookings").where(filter=FieldFilter("customer_phone", "==", phone.strip())).stream()
    
    # Sort in-memory to find latest
    found_bookings = [doc.to_dict() for doc in docs]
    if not found_bookings:
        return None
        
    # Sort by created_at or check_in. Booking model has check_in.
    def _sort_key(b):
        ts = b.get('check_in')
        if isinstance(ts, datetime):
            return ts.timestamp()
        return 0.0
        
    found_bookings.sort(key=_sort_key, reverse=True)
    
    latest = found_bookings[0]
    return {
        "customer_name": latest.get("customer_name"),
        "customer_phone": latest.get("customer_phone"), # Giữ nguyên
        "customer_type": latest.get("customer_type", "Khách lẻ")
    }
    

    return None

def create_user(user_data: dict):
    """Tạo mới hoặc cập nhật user"""
    db = get_db()
    username = user_data.get("username")
    if username:
        db.collection("users").document(username).set(user_data)

def delete_user(username: str):
    """Xóa user"""
    db = get_db()
    if username:
        db.collection("users").document(username).delete()

def create_user_session(username: str) -> str:
    """Tạo session token mới cho user và lưu vào DB"""
    db = get_db()
    token = str(uuid.uuid4())
    # Lưu token vào document của user
    db.collection("users").document(username).update({
        "session_token": token,
        "last_login": datetime.now()
    })
    return token

def verify_user_session(token: str):
    """Kiểm tra token hợp lệ và trả về user info"""
    if not token:
        return None
    
    db = get_db()
    # Tìm user có session_token khớp
    docs = db.collection("users").where(filter=FieldFilter("session_token", "==", token)).limit(1).stream()
    
    for doc in docs:
        user_data = doc.to_dict()
        if user_data.get("is_active", True):
            return user_data
            
    return None

def delete_user_session(username: str):
    """Xóa session token khi logout"""
    if not username: 
        return
    db = get_db()
    try:
        db.collection("users").document(username).update({
            "session_token": firestore.DELETE_FIELD
        })
    except Exception:
        pass

def authenticate_user(username, password):
    """
    Xác thực người dùng. 
    Trả về dict user nếu thành công, None nếu thất bại.
    """
    user = get_user(username)
    if user and user.get("is_active", True):
        # So sánh hash
        if user.get("password_hash") == hash_password(password):
            return user
    return None

def update_user_password(username: str, new_password: str):
    """Đổi mật khẩu"""
    if not username:
        return
    db = get_db()
    new_hash = hash_password(new_password)
    db.collection("users").document(username).update({"password_hash": new_hash})

def get_all_users():
    """Lấy danh sách tất cả users"""
    db = get_db()
    docs = db.collection("users").stream()
    return [doc.to_dict() for doc in docs]

# --- 6. SERVICES & ORDERS ---

def get_all_services():
    """Lấy danh sách Menu dịch vụ"""
    db = get_db()
    docs = db.collection("services").where(filter=FieldFilter("is_active", "==", True)).stream()
    return [doc.to_dict() for doc in docs]

def save_service(service_data: dict):
    """Lưu món ăn/dịch vụ"""
    db = get_db()
    if not service_data.get("id"):
        service_data["id"] = str(uuid.uuid4())[:8]
    db.collection("services").document(service_data["id"]).set(service_data)

def delete_service(service_id: str):
    """Xóa (hoặc ẩn) món ăn"""
    db = get_db()
    # Soft delete: update is_active = False 
    # Nhưng user yêu cầu xóa: Delete luôn hoặc ẩn tùy logic. Ở đây làm ẩn an toàn hơn.
    # Nhưng để đơn giản UI quản lý, ta delete luôn document nếu muốn.
    # Thôi làm soft delete cho an toàn: set is_active=False? 
    # Nhưng get_all_services đang filter is_active=True.
    # Ok, delete thật cho gọn.
    db.collection("services").document(service_id).delete()

def add_service_order(order_data: dict):
    """Tạo order dịch vụ mới"""
    db = get_db()
    if not order_data.get("id"):
        order_data["id"] = str(uuid.uuid4())[:8]
    
    # Auto add timestamp
    if not order_data.get("created_at"):
        order_data["created_at"] = datetime.now()
    
    # 1. Lưu Order
    db.collection("service_orders").document(order_data["id"]).set(order_data)
    return True

def get_orders_by_booking(booking_id: str):
    """Lấy danh sách order của 1 booking"""
    db = get_db()
    docs = db.collection("service_orders").where(filter=FieldFilter("booking_id", "==", booking_id)).stream()
    return [doc.to_dict() for doc in docs]

def calculate_service_total(booking_id: str):
    """Tính tổng tiền dịch vụ của booking"""
    orders = get_orders_by_booking(booking_id)
    return sum(o.get("total_value", 0) for o in orders)

def get_recent_service_orders(limit=50):
    """Lấy danh sách các order gần đây nhất (In-memory sort for safety)"""
    db = get_db()
    docs = db.collection("service_orders").stream()
    orders = [doc.to_dict() for doc in docs]
    
    # Sort desc by created_at. Handle missing field safe.
    # Firestore datetime is timezone-aware usually, datetime.now() is usually local naive or aware depending on env.
    # We just want relative order.
    def _sort_key(x):
        ts = x.get('created_at')
        if isinstance(ts, datetime):
            return ts.timestamp()
        return 0.0 # Oldest
        
    orders.sort(key=_sort_key, reverse=True)
    return orders[:limit]

# --- 7. PERMISSION MANAGEMENT ---

def get_role_permissions(role: str):
    """
    Lấy danh sách quyền của một vai trò.
    
    Nếu chưa có cấu hình trong DB, sẽ trả về cấu hình mặc định.
    Trả về: List[str] - danh sách permission values
    """
    from src.models import DEFAULT_ROLE_PERMISSIONS, UserRole
    
    db = get_db()
    doc = db.collection("config_permissions").document(role).get()
    
    if doc.exists:
        data = doc.to_dict()
        return data.get("permissions", [])
    
    # Fallback: Trả về default
    try:
        role_enum = UserRole(role)
        default_perms = DEFAULT_ROLE_PERMISSIONS.get(role_enum, [])
        # Convert Permission enum to string values
        return [p.value if hasattr(p, 'value') else p for p in default_perms]
    except:
        return []

def save_role_permissions(role: str, permissions: list):
    """
    Lưu cấu hình quyền cho một vai trò.
    
    Args:
        role: Vai trò (admin, manager, accountant, receptionist)
        permissions: List các permission values (strings)
    """
    db = get_db()
    db.collection("config_permissions").document(role).set({
        "role": role,
        "permissions": permissions,
        "updated_at": datetime.now()
    })
    # Clear cache if exists
    if hasattr(get_all_role_permissions, 'clear'):
        get_all_role_permissions.clear()

@st.cache_data(ttl=300)  # Cache 5 minutes
def get_all_role_permissions():
    """
    Lấy tất cả cấu hình phân quyền.
    
    Trả về: Dict[str, List[str]] - {role: [permissions]}
    """
    from src.models import UserRole, DEFAULT_ROLE_PERMISSIONS
    
    db = get_db()
    docs = db.collection("config_permissions").stream()
    
    result = {}
    configured_roles = set()
    
    for doc in docs:
        data = doc.to_dict()
        role = data.get("role")
        if role:
            result[role] = data.get("permissions", [])
            configured_roles.add(role)
    
    # Add defaults for roles not yet configured
    for role_enum in UserRole:
        role = role_enum.value
        if role not in configured_roles:
            default_perms = DEFAULT_ROLE_PERMISSIONS.get(role_enum, [])
            result[role] = [p.value if hasattr(p, 'value') else p for p in default_perms]
    
    return result

def init_default_permissions():
    """
    Khởi tạo phân quyền mặc định cho tất cả vai trò nếu chưa có.
    
    Chỉ chạy lần đầu hoặc khi reset cấu hình.
    """
    from src.models import UserRole, DEFAULT_ROLE_PERMISSIONS
    
    db = get_db()
    
    for role_enum in UserRole:
        role = role_enum.value
        doc = db.collection("config_permissions").document(role).get()
        
        # Chỉ tạo nếu chưa có
        if not doc.exists:
            default_perms = DEFAULT_ROLE_PERMISSIONS.get(role_enum, [])
            perm_values = [p.value if hasattr(p, 'value') else p for p in default_perms]
            
            save_role_permissions(role, perm_values)
    
    # Clear cache
    if hasattr(get_all_role_permissions, 'clear'):
        get_all_role_permissions.clear()
