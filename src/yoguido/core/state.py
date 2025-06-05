"""
Reactive state management for InnTelligence
"""

import json
import uuid
import threading
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# Thread-local storage for session context
_session_context = threading.local()

def set_current_session(session_id: str, user_data: Dict[str, Any]):
    """Set the current session context for the thread"""
    _session_context.session_id = session_id
    _session_context.user_data = user_data

def get_current_session_id() -> Optional[str]:
    """Get the current session ID"""
    return getattr(_session_context, "session_id", None)

def get_current_user_data() -> Optional[Dict[str, Any]]:
    """Get the current user data"""
    return getattr(_session_context, "user_data", None)

def clear_current_session():
    """Clear the current session context"""
    if hasattr(_session_context, "session_id"):
        del _session_context.session_id
    if hasattr(_session_context, "user_data"):
        del _session_context.user_data

# Modify StateManager to be session-aware
class StateManager:
    """Session-aware state management system"""
    
    def __init__(self):
        # Map session_id -> state
        self.session_states = {}
        # Global state (shared across sessions)
        self.global_state = {}
        # Subscribers to state changes
        self.subscribers = []
    
    def subscribe_to_changes(self, callback):
        """Register a callback to be notified of state changes"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
        return callback  # Return the callback for easy unsubscribing
    
    def unsubscribe_from_changes(self, callback):
        """Unregister a state change callback"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def register_state_instance(self, state_id: str, instance: Any):
        """Register a state instance with session awareness"""
        session_id = get_current_session_id()
        
        if not session_id:
            # Store in global space if no session
            self.global_state[state_id] = instance
            return
            
        # Initialize session state dictionary if needed
        if session_id not in self.session_states:
            self.session_states[session_id] = {}
            
        # Store instance in session-specific state
        self.session_states[session_id][state_id] = instance
    
    def get_state(self, key: str, default=None) -> Any:
        """Get state value with session awareness"""
        session_id = get_current_session_id()
        
        if session_id:
            # Get session-specific state
            if session_id not in self.session_states:
                self.session_states[session_id] = {}
                
            session_state = self.session_states[session_id]
            if key in session_state:
                return session_state[key]
        
        # Fall back to global state
        return self.global_state.get(key, default)
    
    def set_state(self, key: str, value: Any, global_state: bool = False):
        """Set state value with session awareness"""
        session_id = get_current_session_id()
        
        if global_state or not session_id:
            # Set in global state
            old_value = self.global_state.get(key)
            self.global_state[key] = value
            is_global = True
        else:
            # Set in session-specific state
            if session_id not in self.session_states:
                self.session_states[session_id] = {}
                
            old_value = self.session_states[session_id].get(key)
            self.session_states[session_id][key] = value
            is_global = False
        
        # Notify subscribers about state change
        if old_value != value:
            self._notify_subscribers(key, value, old_value, session_id, is_global)
    
    def _notify_subscribers(self, key, new_value, old_value, session_id, is_global):
        """Notify subscribers about state changes"""
        for callback in self.subscribers:
            try:
                callback({
                    'key': key,
                    'new_value': new_value,
                    'old_value': old_value,
                    'session_id': session_id,
                    'is_global': is_global,
                    'timestamp': datetime.now(timezone.utc)
                })
            except Exception as e:
                print(f"Error notifying subscriber: {e}")
    
    def get_current_state_snapshot(self) -> Dict[str, Any]:
        """Get current state snapshot (global + session)"""
        result = dict(self.global_state)
        
        session_id = get_current_session_id()
        if session_id and session_id in self.session_states:
            # Override with session state (session takes priority)
            result.update(self.session_states[session_id])
            
        return result
    
    @staticmethod
    def notify_change(state_id, name, old_value, value):
        """Static method to notify about state changes from decorators"""
        # Get the state manager instance
        instance = state_manager
        
        # Get session ID
        session_id = get_current_session_id()
        
        # Check if state is global or session-specific
        is_global = False
        if not session_id or (session_id not in instance.session_states) or (state_id not in instance.session_states.get(session_id, {})):
            is_global = True
        
        # Notify subscribers
        instance._notify_subscribers(name, value, old_value, session_id, is_global)
        
        # Also notify via instance's own notification mechanism if it exists
        target_state = None
        if session_id and session_id in instance.session_states:
            target_state = instance.session_states[session_id].get(state_id)
        if not target_state and state_id in instance.global_state:
            target_state = instance.global_state.get(state_id)
            
        if target_state and hasattr(target_state, '_notify_subscribers'):
            target_state._notify_subscribers(name, value, old_value)

# Initialize the session-aware state manager
state_manager = StateManager()

def state(cls):
    """
    Decorator to mark a class as a stateful component and 
    add reactivity to its properties
    """
    # Generate a unique ID for this state class
    state_id = f"state_{cls.__name__}_{uuid.uuid4().hex[:8]}"
    
    # Mark the class as a YoGuido state
    cls._yoguido_state = True
    cls._state_id = state_id
    
    # Cache the original __init__ and __setattr__ methods
    original_init = cls.__init__
    original_setattr = cls.__setattr__ if hasattr(cls, "__setattr__") else object.__setattr__
    
    # Define new __init__ that registers with state manager
    def __init__(self, *args, **kwargs):
        self._subscribers = []
        original_init(self, *args, **kwargs)
    
    # Define new __setattr__ that notifies subscribers on changes
    def __setattr__(self, name, value):
        # Skip internal attrs or when initializing
        if name.startswith('_'):
            original_setattr(self, name, value)
            return
            
        # Get old value if exists
        old_value = getattr(self, name, None) if hasattr(self, name) else None
        
        # Set the new value
        original_setattr(self, name, value)
        
        # Notify subscribers if value changed and not internal
        if old_value != value and hasattr(self, "_subscribers"):
            self._notify_subscribers(name, value, old_value)
            # Also notify the state manager
            StateManager.notify_change(getattr(self.__class__, '_state_id', ''), name, old_value, value)
    
    # Add method to notify subscribers
    def _notify_subscribers(self, name, new_value, old_value):
        for callback in getattr(self, "_subscribers", []):
            try:
                callback({
                    'key': name,
                    'new_value': new_value,
                    'old_value': old_value,
                })
            except Exception as e:
                print(f"Error notifying state subscriber: {e}")
    
    # Method to add subscriber
    def add_subscriber(self, callback):
        if not hasattr(self, "_subscribers"):
            self._subscribers = []
        if callback not in self._subscribers:
            self._subscribers.append(callback)
        return self
    
    # Method to remove subscriber
    def remove_subscriber(self, callback):
        if hasattr(self, "_subscribers") and callback in self._subscribers:
            self._subscribers.remove(callback)
        return self
    
    # Replace methods
    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls._notify_subscribers = _notify_subscribers
    cls.add_subscriber = add_subscriber
    cls.remove_subscriber = remove_subscriber
    
    return cls

def use_state(state_class: Type, **initial_data) -> Any:
    """
    Hook to use a state class in components
    Returns the same instance across re-renders to maintain state
    """
    if not hasattr(state_class, '_yoguido_state'):
        raise ValueError(f"Class {state_class.__name__} is not a YoGuido state class")
    
    state_id = state_class._state_id
    session_id = get_current_session_id()
    
    # Check if instance already exists for this session
    existing_instance = None
    if session_id and session_id in state_manager.session_states:
        existing_instance = state_manager.session_states[session_id].get(state_id)
    elif not session_id:
        existing_instance = state_manager.global_state.get(state_id)
        
    if existing_instance:
        # Update existing instance with any new initial data
        for key, value in initial_data.items():
            if hasattr(existing_instance, key):
                setattr(existing_instance, key, value)
        return existing_instance   
        
    # Create new instance only if none exists
    print(f"🆕 Creating new state instance for {state_id}")
    instance = state_class()  # This will call __init__ which should initialize data
    
    # Set initial data (override defaults if provided)
    for key, value in initial_data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    
    # Register with state manager
    state_manager.register_state_instance(state_id, instance)
    
    return instance

# Functions to manage global state registry
_state_instances = {}

def get_all_states():
    """Return all existing state instances"""
    return _state_instances

def clear_states():
    """Clear all state instances - useful for testing"""
    global _state_instances
    _state_instances = {}
    
    # Also clear session states
    state_manager.session_states = {}
    state_manager.global_state = {}