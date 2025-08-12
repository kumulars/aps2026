/**
 * APS Analytics JavaScript SDK
 * 
 * Advanced client-side analytics tracking with:
 * - Custom event tracking
 * - User journey mapping
 * - A/B testing support
 * - Conversion goal tracking
 * 
 * Usage:
 *   APS.Analytics.track('button_click', { button_name: 'subscribe' });
 *   APS.Analytics.goal('newsletter_signup');
 *   APS.Analytics.startABTest('homepage_variant');
 */

(function(window) {
    'use strict';
    
    // Create APS namespace
    if (!window.APS) {
        window.APS = {};
    }
    
    // Analytics SDK
    window.APS.Analytics = (function() {
        
        // Configuration
        const config = {
            endpoint: '/api/analytics/',
            batchSize: 10,
            flushInterval: 5000, // 5 seconds
            debug: false,
            enabled: true
        };
        
        // State
        let sessionId = null;
        let userId = null;
        let eventQueue = [];
        let pageLoadTime = null;
        let currentABTests = {};
        let journeyStarted = false;
        
        // Initialize
        function init(options = {}) {
            // Merge options
            Object.assign(config, options);
            
            // Get or create session ID
            sessionId = getSessionId();
            
            // Get user ID if logged in
            userId = getUserId();
            
            // Record page load time
            pageLoadTime = performance.now();
            
            // Start user journey tracking
            startUserJourney();
            
            // Set up page unload tracking
            setupPageTracking();
            
            // Set up periodic flush
            setInterval(flushEvents, config.flushInterval);
            
            // Log initialization
            if (config.debug) {
                console.log('APS Analytics initialized', {
                    sessionId: sessionId,
                    userId: userId,
                    config: config
                });
            }
        }
        
        // Session management
        function getSessionId() {
            let id = sessionStorage.getItem('aps_analytics_session');
            if (!id) {
                id = generateUUID();
                sessionStorage.setItem('aps_analytics_session', id);
            }
            return id;
        }
        
        function getUserId() {
            // Try to get from meta tag, global variable, or cookie
            const metaTag = document.querySelector('meta[name="user-id"]');
            if (metaTag) return metaTag.content;
            
            if (window.currentUserId) return window.currentUserId;
            
            return null;
        }
        
        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c === 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
        
        // User journey tracking
        function startUserJourney() {
            if (journeyStarted) return;
            
            journeyStarted = true;
            
            // Track page view with journey context
            track('page_view', {
                url: window.location.href,
                title: document.title,
                referrer: document.referrer,
                load_time: Math.round(pageLoadTime),
                journey_start: true
            });
            
            // Track page interactions
            setupInteractionTracking();
        }
        
        function setupPageTracking() {
            // Track page visibility changes
            document.addEventListener('visibilitychange', function() {
                track('page_visibility', {
                    visible: !document.hidden,
                    timestamp: Date.now()
                });
            });
            
            // Track page unload
            window.addEventListener('beforeunload', function() {
                track('page_unload', {
                    url: window.location.href,
                    time_on_page: Math.round(performance.now() - pageLoadTime)
                });
                
                // Force flush remaining events
                flushEvents(true);
            });
            
            // Track scroll depth
            let maxScroll = 0;
            window.addEventListener('scroll', throttle(function() {
                const scrollPercent = Math.round(
                    (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
                );
                
                if (scrollPercent > maxScroll) {
                    maxScroll = scrollPercent;
                    
                    // Track milestone scroll depths
                    if ([25, 50, 75, 100].includes(scrollPercent)) {
                        track('scroll_depth', {
                            percent: scrollPercent,
                            url: window.location.href
                        });
                    }
                }
            }, 500));
        }
        
        function setupInteractionTracking() {
            // Track clicks on important elements
            document.addEventListener('click', function(e) {
                const element = e.target;
                
                // Track button clicks
                if (element.tagName === 'BUTTON' || element.type === 'submit') {
                    track('button_click', {
                        text: element.textContent.trim().substring(0, 50),
                        id: element.id,
                        class: element.className,
                        url: window.location.href
                    });
                }
                
                // Track link clicks
                if (element.tagName === 'A' && element.href) {
                    track('link_click', {
                        url: element.href,
                        text: element.textContent.trim().substring(0, 50),
                        internal: element.hostname === window.location.hostname
                    });
                }
                
                // Track download links
                if (element.tagName === 'A' && element.href && isDownloadLink(element.href)) {
                    track('download', {
                        url: element.href,
                        file_type: getFileExtension(element.href),
                        text: element.textContent.trim().substring(0, 50)
                    });
                }
            });
            
            // Track form submissions
            document.addEventListener('submit', function(e) {
                const form = e.target;
                track('form_submit', {
                    form_id: form.id,
                    form_class: form.className,
                    action: form.action,
                    method: form.method,
                    field_count: form.elements.length
                });
            });
        }
        
        // Custom event tracking
        function track(eventName, properties = {}, options = {}) {
            if (!config.enabled) return;
            
            // Create event object
            const event = {
                name: eventName,
                category: options.category || 'interaction',
                session_id: sessionId,
                user_id: userId,
                timestamp: new Date().toISOString(),
                properties: {
                    ...properties,
                    user_agent: navigator.userAgent,
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight
                    },
                    screen: {
                        width: screen.width,
                        height: screen.height
                    }
                },
                page_url: window.location.href,
                referrer_url: document.referrer,
                value: options.value || null
            };
            
            // Add to queue
            eventQueue.push(event);
            
            if (config.debug) {
                console.log('Analytics event tracked:', event);
            }
            
            // Flush if queue is full or immediate flush requested
            if (eventQueue.length >= config.batchSize || options.immediate) {
                flushEvents();
            }
        }
        
        // Conversion goal tracking
        function goal(goalName, value = null, properties = {}) {
            track('conversion_goal', {
                goal_name: goalName,
                goal_value: value,
                ...properties
            }, {
                category: 'conversion',
                value: value,
                immediate: true // Goals are important, send immediately
            });
        }
        
        // A/B testing support
        function getABTestVariant(testName) {
            // Check if we already have a variant for this test
            if (currentABTests[testName]) {
                return currentABTests[testName];
            }
            
            // Request variant from server
            fetch(`/api/analytics/ab-test/${testName}/variant/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    user_id: userId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.variant) {
                    currentABTests[testName] = data.variant;
                    
                    // Track participation
                    track('ab_test_participation', {
                        test_name: testName,
                        variant: data.variant
                    }, { category: 'experiment' });
                }
            })
            .catch(error => {
                if (config.debug) {
                    console.error('A/B test error:', error);
                }
            });
            
            return null; // Will be updated async
        }
        
        function abTestConversion(testName, goalName = null) {
            if (!currentABTests[testName]) return;
            
            track('ab_test_conversion', {
                test_name: testName,
                variant: currentABTests[testName],
                goal_name: goalName
            }, { category: 'experiment', immediate: true });
        }
        
        // Event queue management
        function flushEvents(force = false) {
            if (eventQueue.length === 0) return;
            
            const events = [...eventQueue];
            eventQueue = [];
            
            // Send to server
            sendEvents(events, force);
        }
        
        function sendEvents(events, force = false) {
            const payload = {
                events: events,
                session_id: sessionId,
                user_id: userId
            };
            
            if (navigator.sendBeacon && force) {
                // Use sendBeacon for reliable delivery during page unload
                navigator.sendBeacon(
                    config.endpoint + 'events/',
                    JSON.stringify(payload)
                );
            } else {
                // Regular fetch
                fetch(config.endpoint + 'events/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify(payload)
                })
                .catch(error => {
                    if (config.debug) {
                        console.error('Analytics send error:', error);
                    }
                    // Re-queue events on failure
                    eventQueue.unshift(...events);
                });
            }
        }
        
        // Utility functions
        function getCSRFToken() {
            const token = document.querySelector('[name=csrfmiddlewaretoken]');
            return token ? token.value : '';
        }
        
        function isDownloadLink(url) {
            const downloadExtensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar'];
            return downloadExtensions.some(ext => url.toLowerCase().includes(ext));
        }
        
        function getFileExtension(url) {
            return url.split('.').pop().toLowerCase();
        }
        
        function throttle(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        }
        
        // Advanced features
        function setUserProperties(properties) {
            track('user_properties', properties, { category: 'user' });
        }
        
        function identifyUser(userId, properties = {}) {
            window.APS.Analytics.userId = userId;
            track('user_identify', {
                user_id: userId,
                ...properties
            }, { category: 'user', immediate: true });
        }
        
        function trackTiming(category, name, duration) {
            track('timing', {
                timing_category: category,
                timing_name: name,
                duration_ms: duration
            }, { category: 'performance' });
        }
        
        function trackError(error, context = {}) {
            track('javascript_error', {
                error_message: error.message,
                error_stack: error.stack,
                error_line: error.lineno,
                error_column: error.colno,
                error_filename: error.filename,
                ...context
            }, { category: 'error', immediate: true });
        }
        
        // Auto-initialize if DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => init());
        } else {
            init();
        }
        
        // Error tracking
        window.addEventListener('error', function(e) {
            trackError(e.error || e, {
                type: 'uncaught_error',
                url: window.location.href
            });
        });
        
        window.addEventListener('unhandledrejection', function(e) {
            trackError(new Error(e.reason), {
                type: 'unhandled_promise_rejection',
                url: window.location.href
            });
        });
        
        // Public API
        return {
            init: init,
            track: track,
            goal: goal,
            getABTestVariant: getABTestVariant,
            abTestConversion: abTestConversion,
            setUserProperties: setUserProperties,
            identifyUser: identifyUser,
            trackTiming: trackTiming,
            trackError: trackError,
            flush: () => flushEvents(true),
            
            // Configuration
            config: config,
            
            // State (read-only)
            get sessionId() { return sessionId; },
            get userId() { return userId; },
            get currentABTests() { return {...currentABTests}; }
        };
    })();
    
})(window);