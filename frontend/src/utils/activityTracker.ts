const INACTIVITY_TIMEOUT = 15 * 60 * 1000; // 15 minutes in milliseconds
const CHECK_INTERVAL = 30 * 1000; // Check every 30 seconds

class ActivityTracker {
  private lastActivityKey = 'lastActivity';
  private checkInterval: NodeJS.Timeout | null = null;
  private eventListeners: Array<{ event: string; handler: () => void }> = [];
  private onInactivityCallback: (() => void) | null = null;

  /**
   * Update the last activity timestamp
   */
  updateActivity(): void {
    localStorage.setItem(this.lastActivityKey, Date.now().toString());
  }

  /**
   * Check if user has been inactive for more than 15 minutes
   */
  isInactive(): boolean {
    const lastActivity = localStorage.getItem(this.lastActivityKey);
    if (!lastActivity) {
      return true;
    }

    const timeSinceLastActivity = Date.now() - parseInt(lastActivity, 10);
    return timeSinceLastActivity > INACTIVITY_TIMEOUT;
  }

  /**
   * Start tracking user activity
   */
  startTracking(onInactivity: () => void): void {
    // Store callback
    this.onInactivityCallback = onInactivity;

    // Initialize last activity timestamp
    this.updateActivity();

    // Define event handler
    const handleActivity = () => {
      this.updateActivity();
    };

    // Add event listeners for user interactions
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
    events.forEach((event) => {
      window.addEventListener(event, handleActivity);
      this.eventListeners.push({ event, handler: handleActivity });
    });

    // Start interval to check for inactivity
    this.checkInterval = setInterval(() => {
      if (this.isInactive() && this.onInactivityCallback) {
        this.onInactivityCallback();
      }
    }, CHECK_INTERVAL);
  }

  /**
   * Stop tracking and clean up
   */
  stopTracking(): void {
    // Clear interval
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }

    // Remove all event listeners
    this.eventListeners.forEach(({ event, handler }) => {
      window.removeEventListener(event, handler);
    });
    this.eventListeners = [];

    // Clear callback
    this.onInactivityCallback = null;
  }

  /**
   * Clear activity data from localStorage
   */
  clearActivity(): void {
    localStorage.removeItem(this.lastActivityKey);
  }
}

// Export singleton instance
export default new ActivityTracker();