/**
 * Activity Tracker - Theo dõi hoạt động của user
 * Tự động cập nhật last_seen mỗi 30 giây
 * Đặt offline khi user đóng trang
 */

class ActivityTracker {
    constructor() {
        this.updateInterval = 30000; // 30 giây
        this.intervalId = null;
        this.isActive = true;
        
        this.init();
    }
    
    init() {
        // Bắt đầu tracking
        this.startTracking();
        
        // Lắng nghe sự kiện user tương tác
        this.setupEventListeners();
        
        // Xử lý khi đóng trang
        this.setupBeforeUnload();
        
        // Xử lý khi tab không active
        this.setupVisibilityChange();
    }
    
    startTracking() {
        // Cập nhật ngay lập tức
        this.updateActivity();
        
        // Cập nhật định kỳ
        this.intervalId = setInterval(() => {
            if (this.isActive) {
                this.updateActivity();
            }
        }, this.updateInterval);
    }
    
    stopTracking() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }
    
    updateActivity() {
        fetch('/update_activity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Activity updated');
            }
        })
        .catch(error => {
            console.error('Error updating activity:', error);
        });
    }
    
    setOffline() {
        // Sử dụng sendBeacon để đảm bảo request được gửi ngay cả khi đóng trang
        if (navigator.sendBeacon) {
            const formData = new FormData();
            navigator.sendBeacon('/set_offline', formData);
        } else {
            // Fallback cho browsers không hỗ trợ sendBeacon
            fetch('/set_offline', {
                method: 'POST',
                keepalive: true
            }).catch(error => {
                console.error('Error setting offline:', error);
            });
        }
    }
    
    setupEventListeners() {
        // Cập nhật khi user tương tác
        const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
        
        events.forEach(event => {
            document.addEventListener(event, () => {
                this.isActive = true;
            }, { passive: true });
        });
    }
    
    setupBeforeUnload() {
        // Đặt offline khi đóng trang/tab
        window.addEventListener('beforeunload', () => {
            this.setOffline();
        });
        
        // Đặt offline khi unload
        window.addEventListener('unload', () => {
            this.setOffline();
        });
    }
    
    setupVisibilityChange() {
        // Xử lý khi tab không active
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Tab không còn active
                this.isActive = false;
            } else {
                // Tab active trở lại
                this.isActive = true;
                this.updateActivity(); // Cập nhật ngay
            }
        });
    }
}

// Khởi tạo tracker khi DOM ready
document.addEventListener('DOMContentLoaded', function() {
    // Chỉ khởi tạo nếu user đã đăng nhập
    const userElement = document.querySelector('[data-user-logged-in]');
    if (userElement || document.querySelector('.navbar-text')) {
        window.activityTracker = new ActivityTracker();
    }
});

// Export để có thể sử dụng ở nơi khác
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ActivityTracker;
}