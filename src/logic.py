from datetime import datetime, timedelta
import math
from src.models import PriceConfig, BookingType

def calculate_estimated_price(
    check_in: datetime,
    check_out: datetime,
    booking_type: BookingType,
    price_config: dict
) -> float:
    """
    Tính toán tiền phòng dự kiến.
    Đã xử lý lỗi: can't subtract offset-naive and offset-aware datetimes
    """
    if not price_config:
        return 0.0

    # --- FIX LỖI TIMEZONE Ở ĐÂY ---
    # Nếu dữ liệu có múi giờ (từ Firestore), ta xóa múi giờ đi để tính toán như số thuần túy
    if check_in.tzinfo is not None:
        check_in = check_in.replace(tzinfo=None)
    
    if check_out.tzinfo is not None:
        check_out = check_out.replace(tzinfo=None)
    # ------------------------------

    # 1. Giá theo ngày (24h)
    if booking_type == BookingType.DAILY:
        duration = check_out - check_in
        # 86400 giây = 1 ngày
        days = math.ceil(duration.total_seconds() / 86400) 
        if days < 1: days = 1
        return float(price_config.get("daily_price", 0)) * days

    # 2. Giá qua đêm (Cố định)
    elif booking_type == BookingType.OVERNIGHT:
        return float(price_config.get("overnight_price", 0))

    # 3. Giá theo giờ (Phức tạp nhất)
    elif booking_type == BookingType.HOURLY:
        duration = check_out - check_in
        hours = duration.total_seconds() / 3600
        hours_ceil = math.ceil(hours) # 1h15p -> 2h
        
        # Đảm bảo tối thiểu là 1 giờ
        if hours_ceil < 1: hours_ceil = 1
        
        blocks = price_config.get("hourly_blocks", {})
        # blocks dạng: {"1": 50000, "2": 90000...}
        
        key = str(hours_ceil)
        
        if key in blocks:
            return float(blocks[key])
        else:
            # Logic: Nếu ở lố giờ trong bảng giá (VD bảng max 3h, khách ở 5h)
            if blocks:
                # Tìm key lớn nhất
                max_h = max([int(k) for k in blocks.keys()])
                # Giá của giờ lớn nhất
                base_price = float(blocks.get(str(max_h), 0))
                
                # Logic phụ thu thêm giờ (nếu có cấu hình, tạm thời lấy giá max)
                # Có thể mở rộng logic: (hours_ceil - max_h) * phụ_thu_mỗi_giờ
                return base_price
            return 0.0
            
    return 0.0

def get_applicable_price_config(check_in_date: datetime.date, room_type_data: dict, system_config: dict) -> dict:
    """
    Xác định config giá áp dụng cho ngày check-in.
    Thứ tự ưu tiên:
    1. Ngày Lễ (Holidays)
    2. Cuối tuần (Weekends)
    3. Ngày thường
    """
    price_regular = room_type_data.get("pricing", {})
    price_weekend = room_type_data.get("pricing_weekend", {})
    price_holiday = room_type_data.get("pricing_holiday", {})

    # Lấy cấu hình hệ thống
    holidays = system_config.get("holidays", []) # ["2024-04-30", ...]
    # weekends bây giờ là danh sách các ngày trong tuần (0=Mon, 6=Sun)
    weekend_weekdays = system_config.get("weekend_weekdays", []) # [5, 6]

    date_str = check_in_date.strftime("%Y-%m-%d")

    # 1. Kiểm tra Lễ (Holidays - ưu tiên cao nhất)
    # Lễ vẫn dùng danh sách ngày cụ thể
    if date_str in holidays:
        # Nếu có cấu hình giá Lễ thì dùng
        if price_holiday and (price_holiday.get("daily_price", 0) > 0 or price_holiday.get("overnight_price", 0) > 0):
             return price_holiday

    # 2. Kiểm tra Cuối tuần (Weekends - theo thứ trong tuần)
    # 0=Monday, 6=Sunday
    current_weekday = check_in_date.weekday()
    
    if current_weekday in weekend_weekdays:
        if price_weekend and (price_weekend.get("daily_price", 0) > 0 or price_weekend.get("overnight_price", 0) > 0):
            return price_weekend

    # 3. Mặc định
    return price_regular