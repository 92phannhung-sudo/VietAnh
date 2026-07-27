import logging

logger = logging.getLogger("PatientApp")

# Central Action Registry Dictionary
# Key: action_id (str) -> Value: dict with label, handler_func, default_gesture, default_keyword
ACTION_REGISTRY = {}

def register_action(action_id, label, default_gesture=None, default_keyword=None):
    """
    Decorator to register a clinical action in Python code.
    Usage:
        @register_action("ACTION_CAPTURE", "Chụp ảnh bệnh nhân", "SINGLE_TAP", "chụp")
        def handle_capture(main_window):
            main_window.trigger_photo_capture(source="MAPPED_ACTION")
    """
    def decorator(func):
        ACTION_REGISTRY[action_id] = {
            "action_id": action_id,
            "label": label,
            "handler": func,
            "default_gesture": default_gesture,
            "default_keyword": default_keyword
        }
        logger.info(f"[ACTION_REGISTRY] Registered action: {action_id} ('{label}')")
        return func
    return decorator

def get_registered_actions():
    return ACTION_REGISTRY

def dispatch_action(action_id, main_window):
    """
    Finds and executes the registered handler function for the given action_id.
    """
    if action_id in ACTION_REGISTRY:
        action = ACTION_REGISTRY[action_id]
        logger.info(f"[ACTION_DISPATCH] Executing action: {action_id} ('{action['label']}')")
        try:
            action["handler"](main_window)
            return True
        except Exception as e:
            logger.error(f"[ACTION_ERROR] Error executing handler for {action_id}: {str(e)}", exc_info=True)
            return False
    else:
        logger.warning(f"[ACTION_WARN] Unregistered action_id: {action_id}")
        return False

# ==============================================================================
# REGISTERED CLINICAL ACTIONS
# ==============================================================================

@register_action("ACTION_CAPTURE", "Chụp ảnh Bệnh nhân", default_gesture="SINGLE_TAP", default_keyword="chụp")
def handle_capture(main_window):
    main_window.trigger_photo_capture(source="ACTION_MAPPING")

@register_action("ACTION_DELETE_LAST", "Xóa ảnh vừa chụp", default_gesture="DOUBLE_TAP", default_keyword="xóa")
def handle_delete_last(main_window):
    main_window.delete_latest_photo()

@register_action("ACTION_NEXT_PATIENT", "Chuyển bệnh án mới", default_gesture="TRIPLE_TAP", default_keyword="tiếp")
def handle_next_patient(main_window):
    main_window.reset_active_patient()

@register_action("ACTION_VIEW_PHOTO", "Xem lại ảnh vừa chụp", default_gesture="LONG_PRESS", default_keyword="xem")
def handle_view_photo(main_window):
    main_window.open_latest_photo_preview()
