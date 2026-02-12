import streamlit as st

def button_with_tooltip(label: str, tooltip: str, key: str) -> bool:
    """
    Tạo button với tooltip tùy chỉnh không bị che khuất.
    
    Args:
        label: icon hoặc text của button
        tooltip: text hiển thị khi hover
        key: unique key cho button
    
    Returns:
        True nếu button được click
    """
    # Inject custom tooltip CSS nếu chưa có
    if "custom_tooltip_css_loaded" not in st.session_state:
        st.markdown("""
        <style>
        .tooltip-container {
            position: relative;
            display: inline-block;
        }
        
        .tooltip-container .tooltip-text {
            visibility: hidden;
            background-color: #333;
            color: #fff;
            text-align: center;
            padding: 5px 10px;
            border-radius: 6px;
            position: absolute;
            z-index: 2147483647;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
            pointer-events: none;
        }
        
        .tooltip-container .tooltip-text::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: #333 transparent transparent transparent;
        }
        
        .tooltip-container:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
        </style>
        """, unsafe_allow_html=True)
        st.session_state["custom_tooltip_css_loaded"] = True
    
    # Tạo HTML cho button với tooltip
    button_html = f"""
    <div class="tooltip-container">
        <span class="tooltip-text">{tooltip}</span>
    </div>
    """
    
    # Hiển thị tooltip HTML trước button
    st.markdown(button_html, unsafe_allow_html=True)
    
    # Render actual button
    return st.button(label, key=key)
