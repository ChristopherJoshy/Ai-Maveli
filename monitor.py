import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import json
import time
from pathlib import Path

try:
    from database import db_manager
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# Configure Streamlit page
st.set_page_config(
    page_title="Maveli Bot Monitor",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dashboard
st.markdown("""
<style>
.dashboard-text {
    font-family: 'Inter', sans-serif;
    direction: ltr;
}
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
    text-align: center;
}
.status-good {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}
.status-warning {
    background: linear-gradient(135deg, #fdc830 0%, #f37335 100%);
}
.status-error {
    background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
}
</style>
""", unsafe_allow_html=True)

def load_bot_logs():
    """Load bot logs from file"""
    log_file = Path("bot.log")
    if not log_file.exists():
        return []
    
    logs = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f.readlines():
                if line.strip():
                    logs.append(line.strip())
    except Exception as e:
        st.error(f"Error reading log file: {e}")
    
    return logs[-1000:]  # Get last 1000 log entries

def parse_log_entry(log_line):
    """Parse a log entry to extract information"""
    try:
        parts = log_line.split(' - ', 3)
        if len(parts) >= 4:
            timestamp_str = parts[0]
            logger_name = parts[1]
            level = parts[2]
            message = parts[3]
            
            # Parse timestamp
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            
            return {
                'timestamp': timestamp,
                'logger': logger_name,
                'level': level,
                'message': message
            }
    except Exception:
        pass
    
    return None

def get_bot_statistics():
    """Get bot statistics from logs"""
    logs = load_bot_logs()
    stats = {
        'total_logs': len(logs),
        'error_count': 0,
        'warning_count': 0,
        'info_count': 0,
        'user_messages': 0,
        'audio_generations': 0,
        'gemini_requests': 0,
        'last_activity': None,
        'hourly_activity': {},
        'recent_user_messages': []
    }
    
    for log_line in logs:
        entry = parse_log_entry(log_line)
        if not entry:
            continue
        
        # Count by level
        if entry['level'] == 'ERROR':
            stats['error_count'] += 1
        elif entry['level'] == 'WARNING':
            stats['warning_count'] += 1
        elif entry['level'] == 'INFO':
            stats['info_count'] += 1
        
        # Count specific activities
        message = entry['message'].lower()
        if 'received message from user' in message:
            stats['user_messages'] += 1
            # Extract user message details
            try:
                import re
                # Parse pattern: "Received message from user 773052725 (John): Hello world..."
                match = re.search(r'received message from user (\d+) \(([^)]+)\): (.+)', entry['message'])
                if match:
                    user_id = match.group(1)
                    user_name = match.group(2)
                    user_message = match.group(3)
                    
                    stats['recent_user_messages'].append({
                        'timestamp': entry['timestamp'],
                        'user_id': user_id,
                        'user_name': user_name,
                        'message': user_message[:150] + ('...' if len(user_message) > 150 else '')
                    })
            except Exception:
                pass
        elif 'generated audio file' in message:
            stats['audio_generations'] += 1
        elif 'generated gemini response' in message:
            stats['gemini_requests'] += 1
        
        # Track hourly activity
        hour_key = entry['timestamp'].strftime('%Y-%m-%d %H:00')
        stats['hourly_activity'][hour_key] = stats['hourly_activity'].get(hour_key, 0) + 1
        
        # Update last activity
        if stats['last_activity'] is None or entry['timestamp'] > stats['last_activity']:
            stats['last_activity'] = entry['timestamp']
    
    # Keep only last 20 user messages
    stats['recent_user_messages'] = stats['recent_user_messages'][-20:]
    
    return stats

def main():
    st.title("🎭 Maveli Bot Monitoring Dashboard")
    st.markdown('<div class="dashboard-text">', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.header("⚙️ Controls")
    auto_refresh = st.sidebar.checkbox("🔄 Auto Refresh", value=True)
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 60, 10)
    
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.rerun()
    
    # Load statistics
    stats = get_bot_statistics()
    
    # Status indicator
    now = datetime.now()
    if stats['last_activity']:
        time_since_activity = now - stats['last_activity']
        if time_since_activity < timedelta(minutes=5):
            status = "🟢 Active"
            status_class = "status-good"
        elif time_since_activity < timedelta(minutes=30):
            status = "🟡 Slow"
            status_class = "status-warning"
        else:
            status = "🔴 Inactive"
            status_class = "status-error"
    else:
        status = "⚫ Unknown"
        status_class = "status-error"
    
    # Main metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <h3>Bot Status</h3>
            <h2>{status}</h2>
            <p>Last Activity:<br>
            {stats['last_activity'].strftime('%Y-%m-%d %H:%M:%S') if stats['last_activity'] else 'Unknown'}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>User Messages</h3>
            <h2>{stats['user_messages']}</h2>
            <p>Total messages received</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Audio Generated</h3>
            <h2>{stats['audio_generations']}</h2>
            <p>Voice messages created</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h3>AI Responses</h3>
            <h2>{stats['gemini_requests']}</h2>
            <p>Gemini AI calls made</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Charts row
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Log Level Distribution")
        
        log_levels = {
            'INFO': stats['info_count'],
            'WARNING': stats['warning_count'],
            'ERROR': stats['error_count']
        }
        
        fig_pie = px.pie(
            values=list(log_levels.values()),
            names=list(log_levels.keys()),
            title="Log Types",
            color_discrete_map={
                'INFO': '#2E8B57',
                'WARNING': '#FFD700',
                'ERROR': '#DC143C'
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📈 Hourly Activity")
        
        if stats['hourly_activity']:
            hours = sorted(stats['hourly_activity'].keys())
            activity_counts = [stats['hourly_activity'][hour] for hour in hours]
            
            fig_line = px.line(
                x=hours,
                y=activity_counts,
                title="Activity by Hour",
                labels={'x': 'Time', 'y': 'Activity Count'}
            )
            fig_line.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hourly activity data available")
    
    # Recent user messages section
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💬 Recent User Messages")
        
        if stats['recent_user_messages']:
            message_data = []
            for msg in reversed(stats['recent_user_messages'][-10:]):  # Show last 10 messages
                message_data.append({
                    'Time': msg['timestamp'].strftime('%H:%M:%S'),
                    'User': f"{msg['user_name']} ({msg['user_id']})",
                    'Message': msg['message']
                })
            
            if message_data:
                df_messages = pd.DataFrame(message_data)
                st.dataframe(df_messages, use_container_width=True, height=300)
        else:
            st.info("No recent user messages")
    
    with col2:
        st.subheader("🎯 User Engagement")
        
        if stats['recent_user_messages']:
            # Count unique users
            unique_users = len(set(msg['user_id'] for msg in stats['recent_user_messages']))
            total_messages = len(stats['recent_user_messages'])
            
            st.metric("Unique Users", unique_users)
            st.metric("Total Messages", total_messages)
            
            if total_messages > 0:
                avg_msg_length = sum(len(msg['message']) for msg in stats['recent_user_messages']) / total_messages
                st.metric("Avg Message Length", f"{avg_msg_length:.0f} chars")
        else:
            st.info("No user engagement data yet")

    # Recent logs section
    st.markdown("---")
    st.subheader("📝 Recent Logs")
    
    logs = load_bot_logs()
    recent_logs = logs[-50:]  # Show last 50 logs
    
    if recent_logs:
        log_data = []
        for log_line in recent_logs:
            entry = parse_log_entry(log_line)
            if entry:
                log_data.append({
                    'Time': entry['timestamp'].strftime('%H:%M:%S'),
                    'Level': entry['level'],
                    'Message': entry['message'][:100] + ('...' if len(entry['message']) > 100 else '')
                })
        
        if log_data:
            df = pd.DataFrame(log_data)
            st.dataframe(df, use_container_width=True, height=400)
    else:
        st.info("No log entries available")
    
    # System info
    st.markdown("---")
    st.subheader("🖥️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"""
        **Dashboard Information:**
        - Update Time: {now.strftime('%Y-%m-%d %H:%M:%S')}
        - Total Logs: {stats['total_logs']}
        - Log File: {'✅ Available' if Path('bot.log').exists() else '❌ Not Available'}
        """)
    
    with col2:
        st.info(f"""
        **Environment Variables:**
        - TELEGRAM_API_KEY: {'✅ Set' if os.getenv('TELEGRAM_API_KEY') else '❌ Not Available'}
        - GEMINI_API_KEY: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Not Available'}
        - ADMIN_USER_ID: {'✅ Set' if os.getenv('ADMIN_USER_ID') else '❌ Not Available'}
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
