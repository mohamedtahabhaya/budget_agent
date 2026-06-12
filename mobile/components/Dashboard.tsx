import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  Alert
} from 'react-native';
import Svg, { Circle, G } from 'react-native-svg';
import { API_URL } from '../config';
import { THEMES, getCommonStyles, ThemeType } from './Theme';

export default function Dashboard({
  userId,
  theme,
  displayCurrency,
  setDisplayCurrency,
  activeTab
}: {
  userId: string;
  theme: ThemeType;
  displayCurrency: string;
  setDisplayCurrency: (curr: string) => void;
  activeTab: string;
}) {
  const colors = THEMES[theme];
  const commonStyles = getCommonStyles(colors);
  const styles = getStyles(colors);

  const COLORS = colors;
  const COMMON_STYLES = commonStyles;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [goals, setGoals] = useState<any[]>([]);

  const [transactions, setTransactions] = useState<any[]>([]);
  const [selectedTx, setSelectedTx] = useState<any | null>(null);
  const [showBreakdownModal, setShowBreakdownModal] = useState(false);
  const [showEarningsModal, setShowEarningsModal] = useState(false);
  const [viewMode, setViewMode] = useState<'all' | 'personal' | 'shared'>('all');

  const EXCHANGE_RATES: Record<string, number> = {
    MAD: 1,
    EUR: 11,
    USD: 10,
    GBP: 13
  };

  const convertAmount = (amount: number, from: string, to: string): number => {
    const rateFrom = EXCHANGE_RATES[from.toUpperCase()] || 1;
    const rateTo = EXCHANGE_RATES[to.toUpperCase()] || 1;
    const amountInMAD = amount * rateFrom;
    return amountInMAD / rateTo;
  };

  const fetchData = async () => {
    try {
      // Fetch Accounts
      const accountsRes = await fetch(`${API_URL}/accounts`);
      const accountsData = await accountsRes.json();
      setAccounts(Array.isArray(accountsData) ? accountsData : []);



      // Fetch Transactions (higher limit to calculate monthly breakdown and splits)
      const txsRes = await fetch(`${API_URL}/transactions?limit=1000`);
      const txsData = await txsRes.json();
      setTransactions(Array.isArray(txsData) ? txsData : []);

      // Fetch Savings Goals
      try {
        const goalsRes = await fetch(`${API_URL}/savings-goals`);
        const goalsData = await goalsRes.json();
        setGoals(Array.isArray(goalsData) ? goalsData : []);
      } catch (e) {
        setGoals([]);
      }

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchData();
    }
  }, [userId, activeTab]); // Refresh data when switching active profiles or entering dashboard

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleDeleteTransaction = async (txId: number) => {
    Alert.alert(
      "Confirm Delete",
      "Are you sure you want to delete this transaction?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await fetch(`${API_URL}/transactions/${txId}`, {
                method: 'DELETE',
              });
              const data = await res.json();
              if (data.success) {
                Alert.alert("Success", "Transaction deleted successfully.");
                setSelectedTx(null);
                fetchData();
              } else {
                Alert.alert("Error", data.error || "Failed to delete transaction.");
              }
            } catch (error: any) {
              Alert.alert("Error", error.message || "An error occurred.");
            }
          }
        }
      ]
    );
  };

  if (loading) {
    return (
      <View style={styles.loaderContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loaderText}>Loading financial dashboard...</Text>
      </View>
    );
  }

  // Filter by privacy
  const allowedAccounts = accounts.filter(a => 
    a.type.includes('shared') || 
    a.owner_user_id === userId || 
    !a.owner_user_id
  );

  // Filter by view mode
  const filteredAccounts = allowedAccounts.filter(a => {
    if (viewMode === 'personal') {
      return a.owner_user_id === userId && !a.type.includes('shared');
    } else if (viewMode === 'shared') {
      return a.type.includes('shared') || !a.owner_user_id;
    }
    return true; // 'all'
  });

  // Sum balances
  const totalBalanceConverted = filteredAccounts.reduce((sum, a) => {
    const converted = convertAmount(a.balance, a.currency || 'MAD', displayCurrency);
    return sum + converted;
  }, 0);

  // Filter transactions based on visible accounts
  const filteredTransactions = transactions.filter(t => {
    const acc = allowedAccounts.find(a => a.name === t.account_name || a.id === t.account_id);
    if (!acc) return false;
    return filteredAccounts.some(fa => fa.id === acc.id);
  });

  // Filter savings goals
  const visibleGoals = goals.filter(g => {
    // Check linked account permission
    if (g.account_id) {
      const isAllowed = allowedAccounts.some(a => a.id === g.account_id);
      if (!isAllowed) return false;
    }

    if (viewMode === 'personal') {
      if (!g.account_id) return false; // Hide unlinked goals
      return filteredAccounts.some(a => a.id === g.account_id);
    } else if (viewMode === 'shared') {
      if (!g.account_id) return true; // Show unlinked goals
      return filteredAccounts.some(a => a.id === g.account_id);
    }
    return true; // Show all
  });

  const getGreetingName = () => {
    return userId === 'user_mohamed' ? 'Mohamed' : 'Taha';
  };

  const isNotSavings = (t: any) => {
    return t.category_id !== 'cat_savings' && t.category_name !== 'Savings transfer' && t.category_name !== 'cat_savings';
  };

  // Spending Breakdown Calculations (Target Month)
  const currentMonthStr = new Date().toISOString().slice(0, 7); // e.g. "2026-06"
  let targetMonthStr = currentMonthStr;
  
  const hasCurrentMonthTxs = filteredTransactions.some(t => 
    t.date && t.date.startsWith(currentMonthStr) && 
    t.amount > 0
  );
  
  if (!hasCurrentMonthTxs && filteredTransactions.length > 0) {
    const validDates = filteredTransactions
      .filter(t => t.date && t.amount > 0)
      .map(t => t.date);
    if (validDates.length > 0) {
      targetMonthStr = validDates[0].slice(0, 7); // Sorted desc, so first is latest
    }
  }

  const getMonthName = (monthStr: string) => {
    const [year, month] = monthStr.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1, 1);
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  };

  const expenseTransactions = filteredTransactions.filter(t => 
    t.amount > 0 && 
    t.date && 
    t.date.startsWith(targetMonthStr)
  );
  const totalExpense = expenseTransactions.reduce((sum, t) => sum + t.amount, 0);

  const categoryTotals = expenseTransactions.reduce((acc: Record<string, { name: string, icon: string, amount: number }>, t) => {
    const catKey = t.category_id || t.category_name || 'Other';
    if (!acc[catKey]) {
      acc[catKey] = { name: t.category_name || 'Other', icon: t.category_icon || '📝', amount: 0 };
    }
    acc[catKey].amount += t.amount;
    return acc;
  }, {});

  const categoryList = Object.values(categoryTotals).sort((a: any, b: any) => b.amount - a.amount);

  const getCategoryColor = (index: number) => {
    const colorsList = [
      colors.primary,
      colors.accent,
      colors.success,
      colors.warning,
      '#ec4899', // Pink
      '#06b6d4', // Cyan
      '#f97316', // Orange
    ];
    return colorsList[index % colorsList.length];
  };

  // Earnings/Gains Calculations (Target Month)
  const earningTransactions = filteredTransactions.filter(t => 
    t.amount < 0 && 
    t.date && 
    t.date.startsWith(targetMonthStr)
  );
  const totalEarnings = earningTransactions.reduce((sum, t) => sum + Math.abs(t.amount), 0);

  const earningCategoryTotals = earningTransactions.reduce((acc: any, t: any) => {
    const catKey = t.category_id || t.category_name || 'Other';
    if (!acc[catKey]) {
      acc[catKey] = { name: t.category_name || 'Other', icon: t.category_icon || '📝', amount: 0 };
    }
    acc[catKey].amount += Math.abs(t.amount);
    return acc;
  }, {});

  const earningCategoryList = Object.values(earningCategoryTotals).sort((a: any, b: any) => b.amount - a.amount);

  const getEarningCategoryColor = (index: number) => {
    const colorsList = [
      colors.success,
      '#10b981', // Emerald
      '#34d399', // Light Emerald
      '#059669', // Dark Emerald
      '#84cc16', // Lime
      '#06b6d4', // Cyan
      '#14b8a6', // Teal
    ];
    return colorsList[index % colorsList.length];
  };

  // Shared Expenses Split Contributions
  const sharedTransactions = transactions.filter(t => t.is_shared && t.amount > 0);
  const totalShared = sharedTransactions.reduce((sum, t) => sum + t.amount, 0);
  
  const mohamedPaid = sharedTransactions.filter(t => t.paid_by === 'user_mohamed').reduce((sum, t) => sum + t.amount, 0);
  const tahaPaid = sharedTransactions.filter(t => t.paid_by === 'user_taha').reduce((sum, t) => sum + t.amount, 0);

  return (
    <ScrollView
      style={COMMON_STYLES.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />
      }
    >
      <View style={styles.header}>
        <Text style={styles.welcomeText}>Coloc Taha & Mohamed • Hello {getGreetingName()} 👋</Text>
        <Text style={styles.totalBalance}>
          {totalBalanceConverted.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
        </Text>
        <Text style={styles.totalLabel}>Total Available Balance ({displayCurrency})</Text>

        {/* CURRENCY SWITCHER ROW */}
        <View style={styles.currencySwitcher}>
          {['MAD', 'EUR', 'USD', 'GBP'].map(curr => (
            <TouchableOpacity
              key={curr}
              style={[
                styles.currencyBtn,
                displayCurrency === curr && styles.currencyBtnActive
              ]}
              onPress={() => setDisplayCurrency(curr)}
            >
              <Text style={[
                styles.currencyBtnText,
                displayCurrency === curr && styles.currencyBtnTextActive
              ]}>
                {curr}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* VIEW MODE SWITCHER ROW */}
        <View style={[styles.currencySwitcher, { marginTop: 10 }]}>
          {[
            { key: 'all', label: '🌐 All' },
            { key: 'personal', label: '👤 Personal' },
            { key: 'shared', label: '👥 Joint' }
          ].map(mode => (
            <TouchableOpacity
              key={mode.key}
              style={[
                styles.currencyBtn,
                viewMode === mode.key && styles.currencyBtnActive
              ]}
              onPress={() => setViewMode(mode.key as any)}
            >
              <Text style={[
                styles.currencyBtnText,
                viewMode === mode.key && styles.currencyBtnTextActive
              ]}>
                {mode.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>


      {/* ACCOUNTS SECTION */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>💳 Accounts & Balances</Text>
        <View style={styles.accountsGrid}>
          {filteredAccounts.map((a, i) => {
            // Highlight current user's personal account
            const isPersonal = a.owner_user_id === userId;
            return (
              <View
                key={i}
                style={[
                  styles.accountCard,
                  isPersonal && { borderColor: colors.primary, borderWidth: 1.5 }
                ]}
              >
                <Text style={styles.accountName} numberOfLines={1}>
                  {a.name} {isPersonal && '👤'}
                </Text>
                <Text style={[styles.accountBalance, a.balance < 0 && { color: COLORS.danger }]}>
                  {convertAmount(a.balance, a.currency || 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
                </Text>
                <Text style={[styles.accountType, isPersonal && { color: colors.primary }]}>
                  {a.type.replace('_', ' ')}
                </Text>
              </View>
            );
          })}
          {filteredAccounts.length === 0 && (
            <Text style={styles.emptyText}>No accounts registered.</Text>
          )}
        </View>
      </View>

      {/* VISUAL SPENDING & EARNING BREAKDOWNS (SIDE-BY-SIDE DONUTS) */}
      {(totalExpense > 0 || totalEarnings > 0) && (() => {
        const radius = 32;
        const strokeWidth = 8;
        const circumference = 2 * Math.PI * radius;
        const size = (radius + strokeWidth) * 2;
        
        // Expense segments (compact)
        let expAccumulatedPct = 0;
        const expSegments = categoryList.map((c: any, index: number) => {
          const percentage = totalExpense > 0 ? (c.amount / totalExpense) : 0;
          const strokeLength = percentage * circumference;
          const strokeOffset = -expAccumulatedPct * circumference;
          expAccumulatedPct += percentage;
          return {
            ...c,
            percentageVal: Math.round(percentage * 100),
            strokeLength,
            strokeDashoffset: strokeOffset,
            color: getCategoryColor(index)
          };
        });

        // Earning segments (compact)
        let earnAccumulatedPct = 0;
        const earnSegments = earningCategoryList.map((c: any, index: number) => {
          const percentage = totalEarnings > 0 ? (c.amount / totalEarnings) : 0;
          const strokeLength = percentage * circumference;
          const strokeOffset = -earnAccumulatedPct * circumference;
          earnAccumulatedPct += percentage;
          return {
            ...c,
            percentageVal: Math.round(percentage * 100),
            strokeLength,
            strokeDashoffset: strokeOffset,
            color: getCategoryColor(index)
          };
        });

        // Larger SVG variables for detail modals
        const largeRadius = 60;
        const largeStrokeWidth = 15;
        const largeCircumference = 2 * Math.PI * largeRadius;
        const largeSize = (largeRadius + largeStrokeWidth) * 2;
        
        let largeExpAccumulated = 0;
        const largeExpSegments = categoryList.map((c: any, index: number) => {
          const percentage = totalExpense > 0 ? (c.amount / totalExpense) : 0;
          const strokeLength = percentage * largeCircumference;
          const strokeOffset = -largeExpAccumulated * largeCircumference;
          largeExpAccumulated += percentage;
          return {
            ...c,
            percentage: Math.round(percentage * 100),
            strokeLength,
            strokeDashoffset: strokeOffset,
            color: getCategoryColor(index)
          };
        });

        let largeEarnAccumulated = 0;
        const largeEarnSegments = earningCategoryList.map((c: any, index: number) => {
          const percentage = totalEarnings > 0 ? (c.amount / totalEarnings) : 0;
          const strokeLength = percentage * largeCircumference;
          const strokeOffset = -largeEarnAccumulated * largeCircumference;
          largeEarnAccumulated += percentage;
          return {
            ...c,
            percentage: Math.round(percentage * 100),
            strokeLength,
            strokeDashoffset: strokeOffset,
            color: getCategoryColor(index)
          };
        });

        return (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>📊 Monthly Breakdown • {getMonthName(targetMonthStr)}</Text>
            
            <View style={[COMMON_STYLES.card, { paddingBottom: 15 }]}>
              {/* Row for the two side-by-side compact donuts */}
              <View style={styles.doubleDonutsRow}>
                {/* Left Donut: Expenses */}
                <TouchableOpacity
                  style={styles.compactDonutCard}
                  onPress={() => setShowBreakdownModal(true)}
                  activeOpacity={0.8}
                  disabled={totalExpense === 0}
                >
                  <Text style={styles.donutCardTitle}>Expenses 🔻</Text>
                  {totalExpense > 0 ? (
                    <View style={styles.svgWrapper}>
                      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                        <G rotation="-90" origin={`${size / 2}, ${size / 2}`}>
                          <Circle
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            stroke={COLORS.cardSecondary}
                            strokeWidth={strokeWidth}
                            fill="transparent"
                          />
                          {expSegments.map((seg, i) => (
                            <Circle
                              key={i}
                              cx={size / 2}
                              cy={size / 2}
                              r={radius}
                              stroke={seg.color}
                              strokeWidth={strokeWidth}
                              strokeDasharray={[seg.strokeLength, circumference]}
                              strokeDashoffset={seg.strokeDashoffset}
                              fill="transparent"
                            />
                          ))}
                        </G>
                      </Svg>
                      <View style={styles.centerTextContainer}>
                        <Text style={styles.centerTextAmount} numberOfLines={1} adjustsFontSizeToFit>
                          {convertAmount(totalExpense, 'MAD', displayCurrency).toLocaleString('fr-FR', { maximumFractionDigits: 0 })}
                        </Text>
                        <Text style={styles.centerTextCurrency}>{displayCurrency}</Text>
                      </View>
                    </View>
                  ) : (
                    <Text style={styles.emptyDonutText}>0 {displayCurrency}</Text>
                  )}
                  <Text style={styles.tapDetailsTextCompact}>Details 🔍</Text>
                </TouchableOpacity>

                {/* Right Donut: Earnings */}
                <TouchableOpacity
                  style={styles.compactDonutCard}
                  onPress={() => setShowEarningsModal(true)}
                  activeOpacity={0.8}
                  disabled={totalEarnings === 0}
                >
                  <Text style={styles.donutCardTitle}>Earnings 🔺</Text>
                  {totalEarnings > 0 ? (
                    <View style={styles.svgWrapper}>
                      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
                        <G rotation="-90" origin={`${size / 2}, ${size / 2}`}>
                          <Circle
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            stroke={COLORS.cardSecondary}
                            strokeWidth={strokeWidth}
                            fill="transparent"
                          />
                          {earnSegments.map((seg, i) => (
                            <Circle
                              key={i}
                              cx={size / 2}
                              cy={size / 2}
                              r={radius}
                              stroke={seg.color}
                              strokeWidth={strokeWidth}
                              strokeDasharray={[seg.strokeLength, circumference]}
                              strokeDashoffset={seg.strokeDashoffset}
                              fill="transparent"
                            />
                          ))}
                        </G>
                      </Svg>
                      <View style={styles.centerTextContainer}>
                        <Text style={[styles.centerTextAmount, { color: COLORS.success }]} numberOfLines={1} adjustsFontSizeToFit>
                          {convertAmount(totalEarnings, 'MAD', displayCurrency).toLocaleString('fr-FR', { maximumFractionDigits: 0 })}
                        </Text>
                        <Text style={styles.centerTextCurrency}>{displayCurrency}</Text>
                      </View>
                    </View>
                  ) : (
                    <Text style={styles.emptyDonutText}>0 {displayCurrency}</Text>
                  )}
                  <Text style={styles.tapDetailsTextCompact}>Details 🔍</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Detailed Breakdown Modal (Expenses) */}
            <Modal
              visible={showBreakdownModal}
              animationType="slide"
              transparent={true}
              onRequestClose={() => setShowBreakdownModal(false)}
            >
              <View style={styles.modalOverlay}>
                <View style={[styles.modalContent, { maxHeight: '85%' }]}>
                  <View style={styles.modalHeader}>
                    <Text style={styles.modalTitle}>Expense Details • {getMonthName(targetMonthStr)}</Text>
                    <TouchableOpacity onPress={() => setShowBreakdownModal(false)} style={styles.closeButton}>
                      <Text style={styles.closeButtonText}>✕</Text>
                    </TouchableOpacity>
                  </View>

                  <ScrollView contentContainerStyle={styles.modalScroll}>
                    {/* Larger Donut Chart in Modal */}
                    <View style={styles.largeDonutContainer}>
                      <View style={styles.svgWrapper}>
                        <Svg width={largeSize} height={largeSize} viewBox={`0 0 ${largeSize} ${largeSize}`}>
                          <G rotation="-90" origin={`${largeSize / 2}, ${largeSize / 2}`}>
                            <Circle
                              cx={largeSize / 2}
                              cy={largeSize / 2}
                              r={largeRadius}
                              stroke={COLORS.cardSecondary}
                              strokeWidth={largeStrokeWidth}
                              fill="transparent"
                            />
                            {largeExpSegments.map((seg, i) => (
                              <Circle
                                key={i}
                                cx={largeSize / 2}
                                cy={largeSize / 2}
                                r={largeRadius}
                                stroke={seg.color}
                                strokeWidth={largeStrokeWidth}
                                strokeDasharray={[seg.strokeLength, largeCircumference]}
                                strokeDashoffset={seg.strokeDashoffset}
                                fill="transparent"
                              />
                            ))}
                          </G>
                        </Svg>
                        <View style={styles.largeCenterTextContainer}>
                          <Text style={styles.largeCenterTextAmount} numberOfLines={1} adjustsFontSizeToFit>
                            {convertAmount(totalExpense, 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                          </Text>
                          <Text style={styles.largeCenterTextCurrency}>{displayCurrency}</Text>
                        </View>
                      </View>
                    </View>

                    {/* Detailed Category Legend */}
                    <View style={styles.modalLegendContainer}>
                      {largeExpSegments.map((seg, index) => {
                        const convertedAmount = convertAmount(seg.amount, 'MAD', displayCurrency);
                        return (
                          <View key={index} style={styles.legendRow}>
                            <View style={styles.legendLabelLeft}>
                              <View style={[styles.legendDot, { backgroundColor: seg.color }]} />
                              <Text style={styles.legendText} numberOfLines={1}>
                                {seg.icon} {seg.name}
                              </Text>
                            </View>
                            <Text style={styles.legendValue}>
                              {convertedAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency} ({seg.percentage}%)
                            </Text>
                          </View>
                        );
                      })}
                    </View>

                    {/* Category Transactions Breakdown Title */}
                    <Text style={[styles.sectionTitle, { marginTop: 20, marginBottom: 8 }]}>Monthly Transactions</Text>
                    {expenseTransactions.map((tx, idx) => {
                      const convertedAmt = convertAmount(tx.amount, tx.account_currency || 'MAD', displayCurrency);
                      return (
                        <View key={idx} style={styles.modalTxRow}>
                          <Text style={styles.modalTxIcon}>{tx.category_icon || '📝'}</Text>
                          <View style={styles.modalTxDetails}>
                            <Text style={styles.modalTxMerchant}>{tx.merchant}</Text>
                            <Text style={styles.modalTxMeta}>{tx.date} • Paid by {tx.paid_by_name}</Text>
                          </View>
                          <Text style={styles.modalTxAmount}>
                            -{convertedAmt.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
                          </Text>
                        </View>
                      );
                    })}
                  </ScrollView>
                </View>
              </View>
            </Modal>

            {/* Detailed Breakdown Modal (Earnings) */}
            <Modal
              visible={showEarningsModal}
              animationType="slide"
              transparent={true}
              onRequestClose={() => setShowEarningsModal(false)}
            >
              <View style={styles.modalOverlay}>
                <View style={[styles.modalContent, { maxHeight: '85%' }]}>
                  <View style={styles.modalHeader}>
                    <Text style={styles.modalTitle}>Earning Details • {getMonthName(targetMonthStr)}</Text>
                    <TouchableOpacity onPress={() => setShowEarningsModal(false)} style={styles.closeButton}>
                      <Text style={styles.closeButtonText}>✕</Text>
                    </TouchableOpacity>
                  </View>

                  <ScrollView contentContainerStyle={styles.modalScroll}>
                    {/* Larger Donut Chart in Modal */}
                    <View style={styles.largeDonutContainer}>
                      <View style={styles.svgWrapper}>
                        <Svg width={largeSize} height={largeSize} viewBox={`0 0 ${largeSize} ${largeSize}`}>
                          <G rotation="-90" origin={`${largeSize / 2}, ${largeSize / 2}`}>
                            <Circle
                              cx={largeSize / 2}
                              cy={largeSize / 2}
                              r={largeRadius}
                              stroke={COLORS.cardSecondary}
                              strokeWidth={largeStrokeWidth}
                              fill="transparent"
                            />
                            {largeEarnSegments.map((seg, i) => (
                              <Circle
                                key={i}
                                cx={largeSize / 2}
                                cy={largeSize / 2}
                                r={largeRadius}
                                stroke={seg.color}
                                strokeWidth={largeStrokeWidth}
                                strokeDasharray={[seg.strokeLength, largeCircumference]}
                                strokeDashoffset={seg.strokeDashoffset}
                                fill="transparent"
                              />
                            ))}
                          </G>
                        </Svg>
                        <View style={styles.largeCenterTextContainer}>
                          <Text style={[styles.largeCenterTextAmount, { color: COLORS.success }]} numberOfLines={1} adjustsFontSizeToFit>
                            {convertAmount(totalEarnings, 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
                          </Text>
                          <Text style={styles.largeCenterTextCurrency}>{displayCurrency}</Text>
                        </View>
                      </View>
                    </View>

                    {/* Detailed Category Legend */}
                    <View style={styles.modalLegendContainer}>
                      {largeEarnSegments.map((seg, index) => {
                        const convertedAmount = convertAmount(seg.amount, 'MAD', displayCurrency);
                        return (
                          <View key={index} style={styles.legendRow}>
                            <View style={styles.legendLabelLeft}>
                              <View style={[styles.legendDot, { backgroundColor: seg.color }]} />
                              <Text style={styles.legendText} numberOfLines={1}>
                                {seg.icon} {seg.name}
                              </Text>
                            </View>
                            <Text style={styles.legendValue}>
                              {convertedAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency} ({seg.percentage}%)
                            </Text>
                          </View>
                        );
                      })}
                    </View>

                    {/* Category Transactions Breakdown Title */}
                    <Text style={[styles.sectionTitle, { marginTop: 20, marginBottom: 8 }]}>Monthly Earnings</Text>
                    {earningTransactions.map((tx, idx) => {
                      const convertedAmt = convertAmount(Math.abs(tx.amount), tx.account_currency || 'MAD', displayCurrency);
                      return (
                        <View key={idx} style={styles.modalTxRow}>
                          <Text style={styles.modalTxIcon}>{tx.category_icon || '📝'}</Text>
                          <View style={styles.modalTxDetails}>
                            <Text style={styles.modalTxMerchant}>{tx.merchant}</Text>
                            <Text style={styles.modalTxMeta}>{tx.date} • Received by {tx.paid_by_name}</Text>
                          </View>
                          <Text style={[styles.modalTxAmount, { color: COLORS.success }]}>
                            +{convertedAmt.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
                          </Text>
                        </View>
                      );
                    })}
                  </ScrollView>
                </View>
              </View>
            </Modal>
          </View>
        );
      })()}

      {/* SHARED EXPENSES SPLIT CONTRIBUTIONS */}
      {viewMode !== 'personal' && totalShared > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚖️ Shared Expense Contributions</Text>
          <View style={COMMON_STYLES.card}>
            <View style={styles.contributionRow}>
              <View style={styles.contributionMember}>
                <Text style={styles.contributionName}>Mohamed</Text>
                <Text style={styles.contributionAmount}>
                  {convertAmount(mohamedPaid, 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency} paid
                </Text>
              </View>
              <View style={styles.contributionMember}>
                <Text style={[styles.contributionName, { textAlign: 'right' }]}>Taha</Text>
                <Text style={[styles.contributionAmount, { textAlign: 'right' }]}>
                  {convertAmount(tahaPaid, 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency} paid
                </Text>
              </View>
            </View>
            <View style={styles.contributionBarContainer}>
              <View style={[styles.contributionBarFillLeft, { width: `${totalShared > 0 ? (mohamedPaid / totalShared) * 100 : 50}%`, backgroundColor: colors.primary }]} />
              <View style={[styles.contributionBarFillRight, { width: `${totalShared > 0 ? (tahaPaid / totalShared) * 100 : 50}%`, backgroundColor: colors.accent }]} />
            </View>
            <Text style={styles.contributionSubtext}>
              Total Shared Expenses: {convertAmount(totalShared, 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
            </Text>
          </View>
        </View>
      )}

      {/* SAVINGS GOALS SECTION */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🎯 Savings Goals</Text>
        {visibleGoals.map((g, i) => {
          const progress = g.target > 0 ? g.current / g.target : 0;
          const pct = Math.min(Math.round(progress * 100), 100);
          const convertedCurrent = convertAmount(g.current, 'MAD', displayCurrency);
          const convertedTarget = convertAmount(g.target, 'MAD', displayCurrency);
          return (
            <View key={i} style={COMMON_STYLES.card}>
              <View style={styles.goalRow}>
                <Text style={styles.goalName}>{g.name}</Text>
                <Text style={styles.goalTarget}>
                  {convertedCurrent.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} / {convertedTarget.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} {displayCurrency}
                </Text>
              </View>
              <View style={styles.progressBarBg}>
                <View style={[styles.progressBarFill, { width: `${pct}%` }]} />
              </View>
              <Text style={styles.goalPercentage}>{pct}% Completed • Target: {g.target_date}</Text>
            </View>
          );
        })}
        {visibleGoals.length === 0 && (
          <View style={COMMON_STYLES.card}>
            <Text style={styles.emptyText}>No savings goals registered.</Text>
          </View>
        )}
      </View>

      {/* RECENT TRANSACTIONS SECTION */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>💸 Recent Transactions</Text>
        {filteredTransactions.slice(0, 6).map((tx, i) => {
          const isExpense = tx.amount > 0;
          const convertedTxAmount = convertAmount(Math.abs(tx.amount), tx.account_currency || 'MAD', displayCurrency);
          return (
            <TouchableOpacity
              key={i}
              style={styles.txRow}
              onPress={() => setSelectedTx(tx)}
              activeOpacity={0.7}
            >
              <View style={styles.txIconContainer}>
                <Text style={styles.txIcon}>{tx.category_icon || '📝'}</Text>
              </View>
              <View style={styles.txDetails}>
                <Text style={styles.txMerchant}>{tx.merchant}</Text>
                <Text style={styles.txMeta}>
                  {tx.date} • {tx.category_name} • Paid by {tx.paid_by_name}
                </Text>
              </View>
              <View style={styles.txAmountContainer}>
                <Text style={[styles.txAmount, { color: isExpense ? COLORS.danger : COLORS.success }]}>
                  {isExpense ? '-' : '+'}{convertedTxAmount.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
                </Text>
                {tx.is_shared && <Text style={styles.sharedBadge}>shared</Text>}
              </View>
            </TouchableOpacity>
          );
        })}
        {filteredTransactions.length === 0 && (
          <Text style={styles.emptyText}>No transactions recorded yet.</Text>
        )}
      </View>

      {/* Transaction Details Modal */}
      <Modal
        visible={selectedTx !== null}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setSelectedTx(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Transaction Details</Text>
              <TouchableOpacity onPress={() => setSelectedTx(null)} style={styles.closeButton}>
                <Text style={styles.closeButtonText}>✕</Text>
              </TouchableOpacity>
            </View>

            {selectedTx && (
              <ScrollView contentContainerStyle={styles.modalScroll}>
                <View style={styles.detailAmountContainer}>
                  <Text style={styles.detailIcon}>{selectedTx.category_icon || '📝'}</Text>
                  <Text style={[styles.detailAmount, { color: selectedTx.amount > 0 ? COLORS.danger : COLORS.success }]}>
                    {selectedTx.amount > 0 ? '-' : '+'}{convertAmount(Math.abs(selectedTx.amount), selectedTx.account_currency || 'MAD', displayCurrency).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {displayCurrency}
                  </Text>
                  {(() => {
                    const match = selectedTx.note && selectedTx.note.match(/\[([\d\.\-]+)\s*([A-Za-z]+)\s*converted\s*to\s*([A-Za-z]+)\]/);
                    if (match) {
                      const origAmt = Math.abs(parseFloat(match[1]));
                      const origCurr = match[2];
                      if (origCurr !== displayCurrency) {
                        return (
                          <Text style={{ color: COLORS.textMuted, fontSize: 13, marginTop: 4 }}>
                            Original: {selectedTx.amount > 0 ? '-' : '+'}{origAmt.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {origCurr}
                          </Text>
                        );
                      }
                    } else if (selectedTx.account_currency && selectedTx.account_currency !== displayCurrency) {
                      return (
                        <Text style={{ color: COLORS.textMuted, fontSize: 13, marginTop: 4 }}>
                          Original: {selectedTx.amount > 0 ? '-' : '+'}{Math.abs(selectedTx.amount).toLocaleString('fr-FR')} {selectedTx.account_currency}
                        </Text>
                      );
                    }
                    return null;
                  })()}
                  <Text style={styles.detailMerchant}>{selectedTx.merchant}</Text>
                </View>

                <View style={styles.detailList}>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Date</Text>
                    <Text style={styles.detailValue}>{selectedTx.date}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Category</Text>
                    <Text style={styles.detailValue}>{selectedTx.category_name}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Paid By</Text>
                    <Text style={styles.detailValue}>{selectedTx.paid_by_name}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Account</Text>
                    <Text style={styles.detailValue}>{selectedTx.account_name}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Type</Text>
                    <Text style={styles.detailValue}>{selectedTx.is_shared ? 'Shared (50/50 Split)' : 'Personal Expense'}</Text>
                  </View>
                  {selectedTx.note ? (
                    <View style={styles.detailItemVertical}>
                      <Text style={styles.detailLabel}>Note</Text>
                      <Text style={styles.detailValueNote}>{selectedTx.note}</Text>
                    </View>
                  ) : null}
                </View>

                <View style={styles.modalActions}>
                  <TouchableOpacity
                    style={[styles.modalButton, styles.deleteButton]}
                    onPress={() => handleDeleteTransaction(selectedTx.id)}
                  >
                    <Text style={styles.deleteButtonText}>🗑️ Delete Transaction</Text>
                  </TouchableOpacity>
                </View>
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
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
    alignItems: 'center',
    marginVertical: 20,
  },
  welcomeText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: '600',
  },
  totalBalance: {
    color: COLORS.text,
    fontSize: 32,
    fontWeight: 'bold',
    marginVertical: 6,
  },
  totalLabel: {
    color: COLORS.textMuted,
    fontSize: 12,
    letterSpacing: 0.5,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: COLORS.text,
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  accountsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  accountCard: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 14,
    width: '48%',
    marginBottom: 12,
  },
  accountName: {
    color: COLORS.textMuted,
    fontSize: 13,
  },
  accountBalance: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: 'bold',
    marginVertical: 6,
  },
  accountType: {
    color: COLORS.success,
    fontSize: 10,
    textTransform: 'uppercase',
    fontWeight: '600',
  },
  alertCard: {
    borderColor: COLORS.danger,
    backgroundColor: '#221318',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  alertText: {
    color: '#fca5a5',
    fontSize: 13,
  },
  alertTime: {
    color: '#ef4444',
    fontSize: 10,
    marginTop: 4,
  },
  goalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  goalName: {
    color: COLORS.text,
    fontWeight: 'bold',
    fontSize: 14,
  },
  goalTarget: {
    color: COLORS.textMuted,
    fontSize: 13,
  },
  progressBarBg: {
    height: 8,
    backgroundColor: COLORS.cardSecondary,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 6,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: COLORS.success,
  },
  goalPercentage: {
    color: COLORS.textMuted,
    fontSize: 11,
  },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  txIconContainer: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: COLORS.cardSecondary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  txIcon: {
    fontSize: 18,
  },
  txDetails: {
    flex: 1,
  },
  txMerchant: {
    color: COLORS.text,
    fontWeight: 'bold',
    fontSize: 14,
  },
  txMeta: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  txAmountContainer: {
    alignItems: 'flex-end',
  },
  txAmount: {
    fontWeight: 'bold',
    fontSize: 14,
  },
  sharedBadge: {
    color: COLORS.primary,
    fontSize: 10,
    borderWidth: 1,
    borderColor: COLORS.primary,
    borderRadius: 4,
    paddingHorizontal: 4,
    marginTop: 2,
  },
  emptyText: {
    color: COLORS.textMuted,
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: 10,
  },
  // Chart specific styles
  chartCardContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    flexWrap: 'wrap',
    paddingVertical: 12,
  },
  donutContainer: {
    width: 120,
    height: 120,
    justifyContent: 'center',
    alignItems: 'center',
  },
  svgWrapper: {
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  centerTextContainer: {
    position: 'absolute',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    height: 80,
  },
  centerTextAmount: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  centerTextCurrency: {
    color: COLORS.textMuted,
    fontSize: 10,
    fontWeight: '600',
    marginTop: 1,
    textTransform: 'uppercase',
  },
  legendContainer: {
    flex: 1,
    minWidth: 180,
    marginLeft: 12,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border + '15', // very faint border separator
  },
  legendLabelLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  legendText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '500',
  },
  legendValue: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginLeft: 8,
    textAlign: 'right',
  },
  contributionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  contributionMember: {
    flex: 1,
  },
  contributionName: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: 'bold',
  },
  contributionAmount: {
    color: COLORS.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  contributionBarContainer: {
    height: 8,
    flexDirection: 'row',
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: COLORS.cardSecondary,
    marginBottom: 8,
  },
  contributionBarFillLeft: {
    height: '100%',
  },
  contributionBarFillRight: {
    height: '100%',
  },
  contributionSubtext: {
    color: COLORS.textMuted,
    fontSize: 11,
    textAlign: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: COLORS.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    maxHeight: '80%',
    borderTopWidth: 1,
    borderColor: COLORS.border,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  modalTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: 'bold',
  },
  closeButton: {
    padding: 4,
  },
  closeButtonText: {
    color: COLORS.textMuted,
    fontSize: 18,
    fontWeight: 'bold',
  },
  modalScroll: {
    paddingBottom: 20,
  },
  detailAmountContainer: {
    alignItems: 'center',
    marginVertical: 20,
  },
  detailIcon: {
    fontSize: 40,
    marginBottom: 8,
  },
  detailAmount: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  detailMerchant: {
    fontSize: 16,
    color: COLORS.text,
    fontWeight: '600',
  },
  detailList: {
    backgroundColor: COLORS.cardSecondary,
    borderRadius: 12,
    padding: 12,
    marginBottom: 20,
  },
  detailItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  detailItemVertical: {
    paddingVertical: 10,
  },
  detailLabel: {
    color: COLORS.textMuted,
    fontSize: 13,
  },
  detailValue: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '500',
  },
  detailValueNote: {
    color: COLORS.text,
    fontSize: 13,
    marginTop: 4,
    fontStyle: 'italic',
  },
  modalActions: {
    marginBottom: 10,
  },
  modalButton: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  deleteButton: {
    backgroundColor: '#ef4444',
  },
  deleteButtonText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  currencySwitcher: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 14,
    backgroundColor: COLORS.card,
    borderRadius: 20,
    padding: 3,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  currencyBtn: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 17,
  },
  currencyBtnActive: {
    backgroundColor: COLORS.primary,
  },
  currencyBtnText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: 'bold',
  },
  currencyBtnTextActive: {
    color: '#ffffff',
  },
  compactChartCard: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  doubleDonutsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingVertical: 20,
  },
  compactDonutCard: {
    alignItems: 'center',
    width: '45%',
  },
  donutCardTitle: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 10,
    textAlign: 'center',
  },
  emptyDonutText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: '600',
    marginVertical: 40,
    textAlign: 'center',
  },
  tapDetailsTextCompact: {
    color: COLORS.textMuted,
    fontSize: 11,
    fontWeight: '600',
    marginTop: 10,
    textTransform: 'uppercase',
  },
  tapDetailsText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: '500',
    marginTop: 12,
    textAlign: 'center',
  },
  largeDonutContainer: {
    alignSelf: 'center',
    marginVertical: 24,
    width: 160,
    height: 160,
    justifyContent: 'center',
    alignItems: 'center',
  },
  largeCenterTextContainer: {
    position: 'absolute',
    justifyContent: 'center',
    alignItems: 'center',
    width: 110,
    height: 110,
  },
  largeCenterTextAmount: {
    color: COLORS.text,
    fontSize: 22,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  largeCenterTextCurrency: {
    color: COLORS.textMuted,
    fontSize: 11,
    fontWeight: '700',
    marginTop: 2,
    textTransform: 'uppercase',
  },
  modalLegendContainer: {
    backgroundColor: COLORS.cardSecondary,
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
  },
  modalTxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border + '15',
  },
  modalTxIcon: {
    fontSize: 18,
    marginRight: 10,
    width: 24,
    textAlign: 'center',
  },
  modalTxDetails: {
    flex: 1,
  },
  modalTxMerchant: {
    color: COLORS.text,
    fontWeight: '600',
    fontSize: 13,
  },
  modalTxMeta: {
    color: COLORS.textMuted,
    fontSize: 10,
    marginTop: 1,
  },
  modalTxAmount: {
    color: COLORS.danger,
    fontWeight: 'bold',
    fontSize: 13,
    marginLeft: 8,
  },
  legendsRowContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 10,
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.border + '20',
    paddingTop: 15,
  },
  compactLegendColumn: {
    width: '48%',
  },
  legendRowCompact: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  legendTextCompact: {
    color: COLORS.text,
    fontSize: 10,
    fontWeight: '500',
  },
  legendValueCompact: {
    color: COLORS.textMuted,
    fontSize: 9,
    textAlign: 'right',
  },
  emptyLegendText: {
    color: COLORS.textMuted,
    fontSize: 10,
    fontStyle: 'italic',
    textAlign: 'center',
    paddingVertical: 4,
  },
});
