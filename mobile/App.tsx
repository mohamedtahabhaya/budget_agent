import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  SafeAreaView,
  TouchableOpacity,
  StatusBar,
  Keyboard,
  Platform,
  ScrollView,
  Dimensions
} from 'react-native';
import { THEMES, ThemeType } from './components/Theme';
import { API_URL } from './config';
import Dashboard from './components/Dashboard';
import Chat, { Message } from './components/Chat';
import Notifications from './components/Notifications';
import Settings from './components/Settings';

type Tab = 'dashboard' | 'chat' | 'notifications' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [userId, setUserId] = useState<string>('user_mohamed');
  const [themeMode, setThemeMode] = useState<ThemeType>('dark');
  const [displayCurrency, setDisplayCurrency] = useState<string>('MAD');
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [chatMessages, setChatMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: 'Hello! I am your intelligent financial advisor. How can I help you today?'
    }
  ]);
  const [hasUnread, setHasUnread] = useState(false);

  const [containerWidth, setContainerWidth] = useState(Dimensions.get('window').width);
  const scrollViewRef = useRef<ScrollView>(null);
  const isProgrammaticScroll = useRef(false);
  const isSwiping = useRef(false);
  const TABS: Tab[] = ['dashboard', 'chat', 'notifications', 'settings'];

  const handleTabPress = (tab: Tab) => {
    setActiveTab(tab);
    isProgrammaticScroll.current = true;
    isSwiping.current = false;
    const index = TABS.indexOf(tab);
    scrollViewRef.current?.scrollTo({ x: index * containerWidth, animated: true });
    
    // Reset programmatic flag after scroll animation finishes
    setTimeout(() => {
      isProgrammaticScroll.current = false;
    }, 350);
  };

  const handleScroll = (event: any) => {
    // Prevent layout-induced scroll jumps on native platforms when not swiping
    if (Platform.OS !== 'web' && !isSwiping.current) return;
    if (isProgrammaticScroll.current) return;
    
    const contentOffset = event.nativeEvent.contentOffset.x;
    const index = Math.round(contentOffset / containerWidth);
    if (index >= 0 && index < TABS.length) {
      const tab = TABS[index];
      if (tab !== activeTab) {
        setActiveTab(tab);
        if (tab === 'notifications') {
          markAllAsRead();
        }
      }
    }
  };

  const handleLayout = (event: any) => {
    const { width } = event.nativeEvent.layout;
    if (width > 0 && width !== containerWidth) {
      setContainerWidth(width);
    }
  };

  useEffect(() => {
    const index = TABS.indexOf(activeTab);
    scrollViewRef.current?.scrollTo({ x: index * containerWidth, animated: false });
  }, [containerWidth]);

  const checkUnreadNotifications = async () => {
    try {
      const res = await fetch(`${API_URL}/notifications?limit=20`);
      const data = await res.json();
      if (Array.isArray(data)) {
        const unread = data.some((n: any) => !n.is_read);
        setHasUnread(activeTab === 'notifications' ? false : unread);
      }
    } catch (e) {
      // ignore
    }
  };

  const markAllAsRead = async () => {
    try {
      await fetch(`${API_URL}/notifications/read`, { method: 'POST' });
      setHasUnread(false);
    } catch (e) {
      // ignore
    }
  };

  useEffect(() => {
    checkUnreadNotifications();
    const interval = setInterval(checkUnreadNotifications, 10000); // Check every 10 seconds
    return () => clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    const showSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      () => setIsKeyboardVisible(true)
    );
    const hideSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      () => setIsKeyboardVisible(false)
    );

    return () => {
      showSubscription.remove();
      hideSubscription.remove();
    };
  }, []);

  const colors = THEMES[themeMode];

  // Dynamic header status
  const getActiveUserName = () => {
    return userId === 'user_mohamed' ? 'Mohamed' : 'Taha';
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <StatusBar
        barStyle={themeMode === 'dark' ? 'light-content' : 'dark-content'}
        backgroundColor={colors.card}
      />
      
      {/* HEADER TITLE BAR */}
      <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
        <Text style={[styles.headerTitle, { color: colors.text }]}>Budget Agent</Text>
        <View style={[styles.statusBadge, { backgroundColor: colors.cardSecondary, borderColor: colors.border }]}>
          <View style={[styles.statusDot, { backgroundColor: colors.success }]} />
          <Text style={[styles.statusText, { color: colors.text }]}>
            {getActiveUserName()}
          </Text>
        </View>
      </View>

      {/* ACTIVE SCREEN CONTENT (Horizontal swipeable slide) */}
      <View style={styles.content} onLayout={handleLayout}>
        <ScrollView
          ref={scrollViewRef}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          scrollEventThrottle={16}
          onScroll={handleScroll}
          onScrollBeginDrag={() => { isSwiping.current = true; isProgrammaticScroll.current = false; }}
          onMomentumScrollBegin={() => { isSwiping.current = true; }}
          onMomentumScrollEnd={() => { isSwiping.current = false; }}
          style={{ flex: 1 }}
          contentContainerStyle={{ width: containerWidth * 4, height: '100%' }}
        >
          <View style={{ width: containerWidth, height: '100%' }}>
            <Dashboard
              userId={userId}
              theme={themeMode}
              displayCurrency={displayCurrency}
              setDisplayCurrency={setDisplayCurrency}
              activeTab={activeTab}
            />
          </View>
          <View style={{ width: containerWidth, height: '100%' }}>
            <Chat
              userId={userId}
              theme={themeMode}
              messages={chatMessages}
              setMessages={setChatMessages}
            />
          </View>
          <View style={{ width: containerWidth, height: '100%' }}>
            <Notifications
              userId={userId}
              theme={themeMode}
              activeTab={activeTab}
            />
          </View>
          <View style={{ width: containerWidth, height: '100%' }}>
            <Settings
              userId={userId}
              setUserId={setUserId}
              theme={themeMode}
              setTheme={setThemeMode}
              activeTab={activeTab}
            />
          </View>
        </ScrollView>
      </View>

      {/* BOTTOM TAB NAVIGATION BAR */}
      {!isKeyboardVisible && (
        <View style={[styles.tabBar, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          <TouchableOpacity
            style={[styles.tabItem, activeTab === 'dashboard' && { borderTopColor: colors.primary, borderTopWidth: 2 }]}
            onPress={() => handleTabPress('dashboard')}
          >
            <Text style={styles.tabIcon}>📊</Text>
            <Text style={[styles.tabLabel, { color: activeTab === 'dashboard' ? colors.primary : colors.textMuted, fontWeight: activeTab === 'dashboard' ? 'bold' : '500' }]}>
              Dashboard
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeTab === 'chat' && { borderTopColor: colors.primary, borderTopWidth: 2 }]}
            onPress={() => handleTabPress('chat')}
          >
            <Text style={styles.tabIcon}>💬</Text>
            <Text style={[styles.tabLabel, { color: activeTab === 'chat' ? colors.primary : colors.textMuted, fontWeight: activeTab === 'chat' ? 'bold' : '500' }]}>
              Assistant
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeTab === 'notifications' && { borderTopColor: colors.primary, borderTopWidth: 2 }]}
            onPress={() => {
              handleTabPress('notifications');
              markAllAsRead();
            }}
          >
            <View style={styles.tabIconContainer}>
              <Text style={styles.tabIcon}>🔔</Text>
              {hasUnread && <View style={[styles.redDot, { backgroundColor: colors.danger, borderColor: colors.card }]} />}
            </View>
            <Text style={[styles.tabLabel, { color: activeTab === 'notifications' ? colors.primary : colors.textMuted, fontWeight: activeTab === 'notifications' ? 'bold' : '500' }]}>
              Alerts
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.tabItem, activeTab === 'settings' && { borderTopColor: colors.primary, borderTopWidth: 2 }]}
            onPress={() => handleTabPress('settings')}
          >
            <Text style={styles.tabIcon}>⚙️</Text>
            <Text style={[styles.tabLabel, { color: activeTab === 'settings' ? colors.primary : colors.textMuted, fontWeight: activeTab === 'settings' ? 'bold' : '500' }]}>
              Settings
            </Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
    borderWidth: 1,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  content: {
    flex: 1,
  },
  tabBar: {
    height: 64,
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingBottom: 6,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabIcon: {
    fontSize: 20,
    marginBottom: 2,
  },
  tabLabel: {
    fontSize: 11,
  },
  tabIconContainer: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  redDot: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 1,
  },
});
