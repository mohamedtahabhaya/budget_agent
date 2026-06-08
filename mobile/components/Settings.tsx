import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Switch,
  ActivityIndicator,
  Alert
} from 'react-native';
import { API_URL, DEFAULT_WORKSPACE_ID } from '../config';
import { THEMES, getCommonStyles, ThemeType } from './Theme';

export default function Settings({ userId, setUserId, theme, setTheme }: {
  userId: string;
  setUserId: (id: string) => void;
  theme: ThemeType;
  setTheme: (theme: ThemeType) => void;
}) {
  const colors = THEMES[theme];
  const commonStyles = getCommonStyles(colors);
  const styles = getStyles(colors);

  // Shadows to make existing COMMON_STYLES and COLORS code work without changes
  const COLORS = colors;
  const COMMON_STYLES = commonStyles;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Forms states
  const [wsName, setWsName] = useState('');
  const [wsCurrency, setWsCurrency] = useState('MAD');
  const [splitRule, setSplitRule] = useState('equal');
  const [customPct, setCustomPct] = useState<Record<string, string>>({});
  const [members, setMembers] = useState<any[]>([]);

  // Accounts list & Add Account state
  const [accounts, setAccounts] = useState<any[]>([]);
  const [newAccName, setNewAccName] = useState('');
  const [newAccType, setNewAccType] = useState('personal');
  const [newAccBalance, setNewAccBalance] = useState('');
  const [newAccOwner, setNewAccOwner] = useState(userId);
  const [newAccCurrency, setNewAccCurrency] = useState('MAD');

  // Notification Preferences state
  const [prefBudget, setPrefBudget] = useState(true);
  const [prefRec, setPrefRec] = useState(true);
  const [prefCsv, setPrefCsv] = useState(true);
  const [prefPush, setPrefPush] = useState(true);

  // Budget Limits state
  const [budgets, setBudgets] = useState<any[]>([]);
  const [budgetInputs, setBudgetInputs] = useState<Record<string, string>>({});

  // CSV Import state
  const [importAccountSlug, setImportAccountSlug] = useState('');
  const [importBankName, setImportBankName] = useState('');
  const [csvText, setCsvText] = useState('');
  const [importingCsv, setImportingCsv] = useState(false);

  // Set default import account when accounts load
  useEffect(() => {
    if (accounts.length > 0 && !importAccountSlug) {
      setImportAccountSlug(accounts[0].slug);
    }
  }, [accounts]);

  // Sync owner with active profile
  useEffect(() => {
    setNewAccOwner(userId);
  }, [userId]);

  const fetchSettings = async () => {
    try {
      // Fetch Workspace Settings
      const wsRes = await fetch(`${API_URL}/workspace/${DEFAULT_WORKSPACE_ID}`);
      const wsData = await wsRes.json();
      if (wsData && !wsData.error) {
        setWsName(wsData.name);
        setWsCurrency(wsData.currency);
        setSplitRule(wsData.split_rule);
        setMembers(Array.isArray(wsData.members) ? wsData.members : []);
        
        let pctMap: Record<string, string> = {};
        if (wsData.custom_percentages) {
          Object.keys(wsData.custom_percentages).forEach(k => {
            pctMap[k] = (wsData.custom_percentages[k] * 100).toString();
          });
        }
        setCustomPct(pctMap);
      }

      // Fetch Accounts
      const accsRes = await fetch(`${API_URL}/accounts`);
      const accsData = await accsRes.json();
      setAccounts(Array.isArray(accsData) ? accsData : []);

      // Fetch Notification Preferences
      const prefRes = await fetch(`${API_URL}/preferences/${userId}`);
      const prefData = await prefRes.json();
      if (prefData && !prefData.error) {
        setPrefBudget(prefData.budget_alerts_enabled);
        setPrefRec(prefData.recurring_tx_enabled);
        setPrefCsv(prefData.csv_import_enabled);
        setPrefPush(prefData.browser_push_enabled);
      }

      // Fetch Budget Limits
      const budgetRes = await fetch(`${API_URL}/budgets`);
      const budgetData = await budgetRes.json();
      if (Array.isArray(budgetData)) {
        setBudgets(budgetData);
        let inputs: Record<string, string> = {};
        budgetData.forEach(b => {
          inputs[b.category_id] = b.monthly_cap.toString();
        });
        setBudgetInputs(inputs);
      }

    } catch (e) {
      console.error('Error fetching settings:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, [userId]);

  const saveWorkspaceSettings = async () => {
    setSaving(true);
    try {
      // Validate Custom Splits if active
      let customPercentages: Record<string, number> = {};
      if (splitRule === 'custom') {
        let total = 0;
        for (const member of members) {
          const val = parseFloat(customPct[member.id] || '0');
          if (isNaN(val) || val < 0) {
            Alert.alert('Error', `Invalid percentage for ${member.name}`);
            setSaving(false);
            return;
          }
          total += val;
          customPercentages[member.id] = val / 100; // Save as fraction
        }
        if (Math.abs(total - 100) > 0.1) {
          Alert.alert('Error', `Custom splits must sum to exactly 100%. Got ${total}%`);
          setSaving(false);
          return;
        }
      }

      const res = await fetch(`${API_URL}/workspace/${DEFAULT_WORKSPACE_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: wsName,
          currency: wsCurrency,
          split_rule: splitRule,
          custom_percentages: splitRule === 'custom' ? customPercentages : null
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert('Success', 'Workspace settings saved successfully!');
        fetchSettings();
      } else {
        Alert.alert('Error', data.error || 'Failed to save settings.');
      }
    } catch (e) {
      Alert.alert('Error', 'Connection error.');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdatePreferences = async (key: string, val: boolean) => {
    // Optimistic UI updates
    if (key === 'budget') setPrefBudget(val);
    if (key === 'rec') setPrefRec(val);
    if (key === 'csv') setPrefCsv(val);
    if (key === 'push') setPrefPush(val);

    try {
      await fetch(`${API_URL}/preferences/${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          budget_alerts_enabled: key === 'budget' ? val : prefBudget,
          recurring_tx_enabled: key === 'rec' ? val : prefRec,
          csv_import_enabled: key === 'csv' ? val : prefCsv,
          browser_push_enabled: key === 'push' ? val : prefPush,
        })
      });
    } catch (e) {
      console.error('Error updating preferences:', e);
    }
  };

  const handleCreateAccount = async () => {
    if (!newAccName.trim() || !newAccBalance) {
      Alert.alert('Error', 'Provide name and initial balance.');
      return;
    }
    try {
      const res = await fetch(`${API_URL}/accounts/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: DEFAULT_WORKSPACE_ID,
          name: newAccName,
          type: newAccType,
          owner_user_id: newAccOwner,
          currency: newAccCurrency,
          balance: parseFloat(newAccBalance)
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert('Success', 'Account created successfully!');
        setNewAccName('');
        setNewAccBalance('');
        setNewAccCurrency('MAD'); // Reset currency to default
        fetchSettings();
      } else {
        Alert.alert('Error', data.error || 'Failed to create account.');
      }
    } catch (e) {
      Alert.alert('Error', 'Connection error.');
    }
  };

  const handleArchiveAccount = (slug: string, name: string) => {
    Alert.alert('Archive Account', `Are you sure you want to archive '${name}'?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Archive',
        style: 'destructive',
        onPress: async () => {
          try {
            const res = await fetch(`${API_URL}/accounts/${slug}/archive`, {
              method: 'POST'
            });
            const data = await res.json();
            if (data.success) {
              Alert.alert('Success', 'Account archived!');
              fetchSettings();
            }
          } catch (e) {
            Alert.alert('Error', 'Connection error.');
          }
        }
      }
    ]);
  };

  const handleSaveBudgetLimit = async (catId: string) => {
    const val = budgetInputs[catId] || '0';
    try {
      const res = await fetch(`${API_URL}/budgets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category_id: catId,
          monthly_cap: parseFloat(val),
          scope_type: 'workspace'
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert('Success', 'Budget limit updated!');
        fetchSettings();
      } else {
        Alert.alert('Error', data.error || 'Failed to update budget.');
      }
    } catch (e) {
      Alert.alert('Error', 'Connection error.');
    }
  };

  const handleImportCSV = async () => {
    if (!importAccountSlug) {
      Alert.alert('Error', 'Please select a target account.');
      return;
    }
    if (!csvText.trim()) {
      Alert.alert('Error', 'Please paste some CSV content to import.');
      return;
    }

    setImportingCsv(true);
    try {
      const res = await fetch(`${API_URL}/import-bank-csv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          csv_content: csvText,
          account_slug: importAccountSlug,
          workspace_id: DEFAULT_WORKSPACE_ID,
          bank_name: importBankName || null
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert('Import Success', data.message || 'CSV imported successfully!');
        setCsvText(''); // Clear input
        fetchSettings(); // Refresh accounts balance
      } else {
        Alert.alert('Import Failed', data.error || 'Failed to import CSV.');
      }
    } catch (e) {
      Alert.alert('Error', 'Connection error.');
    } finally {
      setImportingCsv(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loaderContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loaderText}>Loading workspace settings...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={COMMON_STYLES.container} contentContainerStyle={styles.content}>
      <Text style={styles.pageTitle}>Workspace Settings</Text>

      {/* PROFILE & THEME SETTINGS CARD */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>👤 Profile & App Style</Text>
        
        <Text style={styles.label}>Active User Profile</Text>
        <View style={styles.selectorRow}>
          <TouchableOpacity
            style={[
              styles.selectorBtn,
              userId === 'user_mohamed' && styles.selectorBtnActive
            ]}
            onPress={() => setUserId('user_mohamed')}
          >
            <Text style={[styles.selectorBtnText, userId === 'user_mohamed' && styles.selectorBtnTextActive]}>
              Mohamed
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.selectorBtn,
              userId === 'user_taha' && styles.selectorBtnActive
            ]}
            onPress={() => setUserId('user_taha')}
          >
            <Text style={[styles.selectorBtnText, userId === 'user_taha' && styles.selectorBtnTextActive]}>
              Taha
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.label}>App Theme Mode</Text>
        <View style={styles.selectorRow}>
          <TouchableOpacity
            style={[
              styles.selectorBtn,
              theme === 'dark' && styles.selectorBtnActive
            ]}
            onPress={() => setTheme('dark')}
          >
            <Text style={[styles.selectorBtnText, theme === 'dark' && styles.selectorBtnTextActive]}>
              Dark Mode 🌙
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.selectorBtn,
              theme === 'light' && styles.selectorBtnActive
            ]}
            onPress={() => setTheme('light')}
          >
            <Text style={[styles.selectorBtnText, theme === 'light' && styles.selectorBtnTextActive]}>
              Light Mode ☀️
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* WORKSPACE PREFERENCES CARD */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>🏢 Workspace Configuration</Text>
        
        <Text style={styles.label}>Workspace Name</Text>
        <TextInput
          style={COMMON_STYLES.input}
          value={wsName}
          onChangeText={setWsName}
          placeholder="Name"
          placeholderTextColor={COLORS.textMuted}
        />

        <Text style={styles.label}>Default Currency</Text>
        <View style={styles.selectorRow}>
          {['MAD', 'EUR', 'USD', 'GBP'].map(curr => (
            <TouchableOpacity
              key={curr}
              style={[
                styles.selectorBtn,
                wsCurrency === curr && styles.selectorBtnActive
              ]}
              onPress={() => setWsCurrency(curr)}
            >
              <Text style={[
                styles.selectorBtnText,
                wsCurrency === curr && styles.selectorBtnTextActive
              ]}>
                {curr}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Split Rule Mode ({splitRule})</Text>
        <View style={styles.splitRuleRow}>
          {['equal', 'proportional', 'custom'].map(rule => (
            <TouchableOpacity
              key={rule}
              style={[
                styles.splitRuleBtn,
                splitRule === rule && styles.splitRuleBtnActive
              ]}
              onPress={() => setSplitRule(rule)}
            >
              <Text style={styles.splitRuleBtnText}>{rule}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {splitRule === 'custom' && (
          <View style={styles.customSplitsContainer}>
            <Text style={styles.label}>Custom Splits Percentages (%)</Text>
            {members.map(member => (
              <View key={member.id} style={styles.memberPctRow}>
                <Text style={styles.memberName}>{member.name}</Text>
                <TextInput
                  style={styles.pctInput}
                  value={customPct[member.id] || ''}
                  onChangeText={(val) => setCustomPct(prev => ({ ...prev, [member.id]: val }))}
                  keyboardType="numeric"
                  placeholder="50"
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>
            ))}
          </View>
        )}

        <TouchableOpacity style={COMMON_STYLES.button} onPress={saveWorkspaceSettings} disabled={saving}>
          {saving ? (
            <ActivityIndicator size="small" color={COLORS.text} />
          ) : (
            <Text style={COMMON_STYLES.buttonText}>Save Configuration</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* NOTIFICATION PREFERENCES CARD */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>⚙️ Notification Preferences</Text>
        
        <View style={styles.switchRow}>
          <View style={styles.switchLabelContainer}>
            <Text style={styles.switchLabel}>Budget Alerts</Text>
            <Text style={styles.switchDesc}>Warn when monthly budget caps are breached</Text>
          </View>
          <Switch
            value={prefBudget}
            onValueChange={(val) => handleUpdatePreferences('budget', val)}
            trackColor={{ false: COLORS.border, true: COLORS.primary }}
            thumbColor={prefBudget ? '#ffffff' : '#f4f3f4'}
          />
        </View>

        <View style={styles.switchRow}>
          <View style={styles.switchLabelContainer}>
            <Text style={styles.switchLabel}>Recurring Subscriptions</Text>
            <Text style={styles.switchDesc}>Notify on automated subscription charges</Text>
          </View>
          <Switch
            value={prefRec}
            onValueChange={(val) => handleUpdatePreferences('rec', val)}
            trackColor={{ false: COLORS.border, true: COLORS.primary }}
            thumbColor={prefRec ? '#ffffff' : '#f4f3f4'}
          />
        </View>

        <View style={styles.switchRow}>
          <View style={styles.switchLabelContainer}>
            <Text style={styles.switchLabel}>CSV Statement Imports</Text>
            <Text style={styles.switchDesc}>Log reports when CSV bank files are uploaded</Text>
          </View>
          <Switch
            value={prefCsv}
            onValueChange={(val) => handleUpdatePreferences('csv', val)}
            trackColor={{ false: COLORS.border, true: COLORS.primary }}
            thumbColor={prefCsv ? '#ffffff' : '#f4f3f4'}
          />
        </View>

        <View style={styles.switchRow}>
          <View style={styles.switchLabelContainer}>
            <Text style={styles.switchLabel}>Push Notifications</Text>
            <Text style={styles.switchDesc}>Enable system-level push notifications</Text>
          </View>
          <Switch
            value={prefPush}
            onValueChange={(val) => handleUpdatePreferences('push', val)}
            trackColor={{ false: COLORS.border, true: COLORS.primary }}
            thumbColor={prefPush ? '#ffffff' : '#f4f3f4'}
          />
        </View>
      </View>

      {/* CATEGORIES BUDGET LIMITS CARD */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>📊 Category Budget Limits</Text>
        {budgets.filter(b => b.kind === 'expense').map(b => (
          <View key={b.category_id} style={styles.budgetLimitRow}>
            <Text style={styles.budgetName}>
              {b.icon} {b.category_name}
            </Text>
            <TextInput
              style={styles.budgetLimitInput}
              value={budgetInputs[b.category_id] || ''}
              onChangeText={(val) => setBudgetInputs(prev => ({ ...prev, [b.category_id]: val }))}
              keyboardType="numeric"
              placeholder="0.0"
              placeholderTextColor={COLORS.textMuted}
            />
            <TouchableOpacity
              style={styles.budgetLimitBtn}
              onPress={() => handleSaveBudgetLimit(b.category_id)}
            >
              <Text style={styles.budgetLimitBtnText}>Save</Text>
            </TouchableOpacity>
          </View>
        ))}
      </View>

      {/* CSV BANK STATEMENT UPLOADER CARD */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>📁 CSV Bank Statement Uploader</Text>
        <Text style={styles.switchDesc}>
          Paste transaction logs directly from your bank's export (supports Attijariwafa, BMCE, SG, etc.).
        </Text>

        <Text style={[styles.label, { marginTop: 12 }]}>Target Account</Text>
        <View style={styles.accountSelectorScroll}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.horizontalScroll}>
            {accounts.map(acc => (
              <TouchableOpacity
                key={acc.slug}
                style={[
                  styles.miniSelectorBtn,
                  importAccountSlug === acc.slug && styles.miniSelectorBtnActive
                ]}
                onPress={() => setImportAccountSlug(acc.slug)}
              >
                <Text style={[styles.miniSelectorBtnText, importAccountSlug === acc.slug && styles.miniSelectorBtnTextActive]}>
                  {acc.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        <Text style={[styles.label, { marginTop: 12 }]}>Bank Format</Text>
        <View style={styles.bankFormatRow}>
          {[
            { id: '', name: 'Auto-Detect 🔍' },
            { id: 'Attijariwafa', name: 'Attijari 🇲🇦' },
            { id: 'BMCE', name: 'BMCE 🇲🇦' },
            { id: 'SG', name: 'SG 🇲🇦' }
          ].map(bank => (
            <TouchableOpacity
              key={bank.id}
              style={[
                styles.miniSelectorBtn,
                importBankName === bank.id && styles.miniSelectorBtnActive,
                { flex: 1, marginHorizontal: 2 }
              ]}
              onPress={() => setImportBankName(bank.id)}
            >
              <Text style={[styles.miniSelectorBtnText, importBankName === bank.id && styles.miniSelectorBtnTextActive, { fontSize: 10 }]}>
                {bank.name}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={[styles.label, { marginTop: 12 }]}>CSV Content</Text>
        <TextInput
          style={[COMMON_STYLES.input, styles.csvInput]}
          value={csvText}
          onChangeText={setCsvText}
          multiline={true}
          numberOfLines={6}
          placeholder={`Date;Libellé;Montant\n01/06/2026;Carrefour;-350.00\n02/06/2026;Salaire;12000.00`}
          placeholderTextColor={COLORS.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
        />

        <TouchableOpacity
          style={[COMMON_STYLES.button, { marginTop: 12 }]}
          onPress={handleImportCSV}
          disabled={importingCsv}
        >
          {importingCsv ? (
            <ActivityIndicator size="small" color={COLORS.text} />
          ) : (
            <Text style={COMMON_STYLES.buttonText}>📤 Process & Import Statement</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* ACCOUNTS LIST & LIFECYCLE */}
      <View style={COMMON_STYLES.card}>
        <Text style={styles.sectionHeader}>💳 Accounts Lifecycle</Text>
        {accounts.map(acc => (
          <View key={acc.slug} style={styles.accountListItem}>
            <View>
              <Text style={styles.accountListName}>{acc.name}</Text>
              <Text style={styles.accountListMeta}>
                {acc.balance.toLocaleString('fr-FR')} {acc.currency} • {acc.type.replace('_', ' ')}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.archiveBtn}
              onPress={() => handleArchiveAccount(acc.slug, acc.name)}
            >
              <Text style={styles.archiveBtnText}>Archive</Text>
            </TouchableOpacity>
          </View>
        ))}

        <Text style={[styles.label, { marginTop: 16 }]}>Create New Account</Text>
        <TextInput
          style={COMMON_STYLES.input}
          value={newAccName}
          onChangeText={setNewAccName}
          placeholder="Account Name (e.g. Card)"
          placeholderTextColor={COLORS.textMuted}
        />
        <TextInput
          style={COMMON_STYLES.input}
          value={newAccBalance}
          onChangeText={setNewAccBalance}
          keyboardType="numeric"
          placeholder="Initial Balance (e.g. 5000)"
          placeholderTextColor={COLORS.textMuted}
        />

        <Text style={styles.label}>Account Type</Text>
        <View style={styles.typeSelectorRow}>
          {['personal', 'shared_current', 'shared_savings'].map(type => (
            <TouchableOpacity
              key={type}
              style={[
                styles.typeBtn,
                newAccType === type && styles.typeBtnActive
              ]}
              onPress={() => setNewAccType(type)}
            >
              <Text style={styles.typeBtnText}>{type.replace('_', ' ')}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Account Currency</Text>
        <View style={styles.selectorRow}>
          {['MAD', 'EUR', 'USD', 'GBP'].map(curr => (
            <TouchableOpacity
              key={curr}
              style={[
                styles.selectorBtn,
                newAccCurrency === curr && styles.selectorBtnActive
              ]}
              onPress={() => setNewAccCurrency(curr)}
            >
              <Text style={[
                styles.selectorBtnText,
                newAccCurrency === curr && styles.selectorBtnTextActive
              ]}>
                {curr}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity style={[COMMON_STYLES.button, { marginTop: 12 }]} onPress={handleCreateAccount}>
          <Text style={COMMON_STYLES.buttonText}>Create Account</Text>
        </TouchableOpacity>
      </View>
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
  pageTitle: {
    color: COLORS.text,
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 20,
  },
  sectionHeader: {
    color: COLORS.text,
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  label: {
    color: COLORS.textMuted,
    fontSize: 12,
    marginBottom: 6,
  },
  splitRuleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
    marginTop: 4,
  },
  splitRuleBtn: {
    backgroundColor: COLORS.cardSecondary,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 8,
    borderRadius: 8,
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  splitRuleBtnActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  splitRuleBtnText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: 'bold',
    textTransform: 'capitalize',
  },
  customSplitsContainer: {
    marginBottom: 16,
    paddingLeft: 8,
    borderLeftWidth: 2,
    borderLeftColor: COLORS.primary,
  },
  memberPctRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  memberName: {
    color: COLORS.text,
    fontSize: 14,
  },
  pctInput: {
    backgroundColor: COLORS.cardSecondary,
    borderColor: COLORS.border,
    borderWidth: 1,
    borderRadius: 8,
    color: COLORS.text,
    width: 60,
    textAlign: 'center',
    padding: 6,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  switchLabelContainer: {
    flex: 1,
    marginRight: 10,
  },
  switchLabel: {
    color: COLORS.text,
    fontWeight: 'bold',
    fontSize: 14,
  },
  switchDesc: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  budgetLimitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  budgetName: {
    color: COLORS.text,
    fontSize: 14,
    flex: 1,
  },
  budgetLimitInput: {
    backgroundColor: COLORS.cardSecondary,
    borderColor: COLORS.border,
    borderWidth: 1,
    borderRadius: 8,
    color: COLORS.text,
    width: 80,
    textAlign: 'center',
    paddingHorizontal: 8,
    paddingVertical: 6,
    marginRight: 8,
  },
  budgetLimitBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  budgetLimitBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
  },
  accountListItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  accountListName: {
    color: COLORS.text,
    fontWeight: 'bold',
    fontSize: 14,
  },
  accountListMeta: {
    color: COLORS.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  archiveBtn: {
    backgroundColor: '#3b1616',
    borderWidth: 1,
    borderColor: COLORS.danger,
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  archiveBtnText: {
    color: COLORS.danger,
    fontSize: 11,
    fontWeight: 'bold',
  },
  typeSelectorRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
    marginTop: 4,
  },
  typeBtn: {
    backgroundColor: COLORS.cardSecondary,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 8,
    borderRadius: 8,
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 3,
  },
  typeBtnActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  typeBtnText: {
    color: COLORS.text,
    fontSize: 10,
    fontWeight: 'bold',
    textTransform: 'capitalize',
  },
  // Selector button styles
  selectorRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
    marginTop: 4,
  },
  selectorBtn: {
    flex: 1,
    backgroundColor: COLORS.cardSecondary,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  selectorBtnActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  selectorBtnText: {
    color: COLORS.textMuted,
    fontSize: 13,
    fontWeight: 'bold',
  },
  selectorBtnTextActive: {
    color: '#ffffff',
  },
  accountSelectorScroll: {
    marginVertical: 4,
  },
  horizontalScroll: {
    paddingVertical: 4,
  },
  miniSelectorBtn: {
    backgroundColor: COLORS.cardSecondary,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    marginRight: 6,
    alignItems: 'center',
  },
  miniSelectorBtnActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  miniSelectorBtnText: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: 'bold',
  },
  miniSelectorBtnTextActive: {
    color: '#ffffff',
  },
  bankFormatRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  csvInput: {
    height: 120,
    textAlignVertical: 'top',
    fontSize: 11,
  },
});
