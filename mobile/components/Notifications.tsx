import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { API_URL } from '../config';
import { THEMES, getCommonStyles, ThemeType } from './Theme';

export default function Notifications({
  userId,
  theme,
}: {
  userId: string;
  theme: ThemeType;
}) {
  const colors = THEMES[theme];
  const commonStyles = getCommonStyles(colors);
  const styles = getStyles(colors);

  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchNotifications = async () => {
    try {
      const res = await fetch(`${API_URL}/notifications?limit=50`);
      const data = await res.json();
      setNotifications(Array.isArray(data) ? data : []);
      try {
        await fetch(`${API_URL}/notifications/read`, { method: 'POST' });
      } catch (e) {
        // ignore
      }
    } catch (error) {
      console.error('Error fetching notifications:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [userId]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchNotifications();
  };

  const getAlertIcon = (message: string) => {
    if (message.includes('CRITICAL')) return '🚨';
    if (message.includes('WARNING')) return '⚠️';
    return '🔔';
  };

  const isCritical = (message: string) => {
    return message.includes('CRITICAL');
  };

  if (loading) {
    return (
      <View style={styles.loaderContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loaderText}>Loading alerts...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={commonStyles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.title}>Notifications Center 🔔</Text>
        <Text style={styles.subtitle}>Recent budget updates and active workspace alerts</Text>
      </View>

      {notifications.length > 0 ? (
        notifications.map((n, i) => {
          const critical = isCritical(n.message);
          return (
            <View
              key={n.id || i}
              style={[
                commonStyles.card,
                styles.notifCard,
                critical ? styles.criticalCard : styles.warningCard
              ]}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.alertIcon}>{getAlertIcon(n.message)}</Text>
                <View style={styles.messageContainer}>
                  <Text style={[styles.messageText, { color: colors.text }]}>
                    {n.message}
                  </Text>
                  <Text style={styles.timestampText}>{n.timestamp}</Text>
                </View>
              </View>
            </View>
          );
        })
      ) : (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>🔔</Text>
          <Text style={[styles.emptyText, { color: colors.text }]}>All clear!</Text>
          <Text style={styles.emptySubtext}>You have no notifications or budget alerts.</Text>
        </View>
      )}
    </ScrollView>
  );
}

const getStyles = (COLORS: any) => StyleSheet.create({
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  loaderContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loaderText: {
    color: COLORS.textMuted,
    marginTop: 12,
    fontSize: 14,
  },
  header: {
    marginBottom: 20,
  },
  title: {
    color: COLORS.text,
    fontSize: 22,
    fontWeight: 'bold',
  },
  subtitle: {
    color: COLORS.textMuted,
    fontSize: 14,
    marginTop: 4,
  },
  notifCard: {
    borderLeftWidth: 4,
    padding: 14,
    marginBottom: 12,
  },
  criticalCard: {
    borderLeftColor: COLORS.danger,
    borderColor: COLORS.border,
  },
  warningCard: {
    borderLeftColor: COLORS.warning,
    borderColor: COLORS.border,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  alertIcon: {
    fontSize: 22,
    marginRight: 12,
    marginTop: 2,
  },
  messageContainer: {
    flex: 1,
  },
  messageText: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '500',
  },
  timestampText: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginTop: 6,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 80,
  },
  emptyIcon: {
    fontSize: 48,
    color: COLORS.textMuted,
    opacity: 0.5,
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  emptySubtext: {
    color: COLORS.textMuted,
    fontSize: 13,
    textAlign: 'center',
  },
});
