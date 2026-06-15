// Orders page — W13 Flutter iOS port of miniprogram/pages/order/.
//
// Shows order list with 6 status tabs: All / Pending Payment / Paid /
// Reviewing / Approved / Rejected. Mock data with realistic orders.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class OrdersPage extends StatefulWidget {
  const OrdersPage({super.key});

  @override
  State<OrdersPage> createState() => _OrdersPageState();
}

class _OrdersPageState extends State<OrdersPage> {
  String _activeTab = 'all';
  bool _loading = false;
  bool _isLoggedIn = false;

  final List<_OrderTab> _tabs = const [
    _OrderTab(key: 'all', labelKey: 'tab_all'),
    _OrderTab(key: 'pending_payment', labelKey: 'tab_pending_payment'),
    _OrderTab(key: 'paid', labelKey: 'tab_paid'),
    _OrderTab(key: 'reviewing', labelKey: 'tab_reviewing'),
    _OrderTab(key: 'approved', labelKey: 'tab_approved'),
    _OrderTab(key: 'rejected', labelKey: 'tab_rejected'),
  ];

  // Mock orders — replace with AuthService / API data in V2.1
  final List<Map<String, dynamic>> _allOrders = [
    {'id': 'ORD-20260601-001', 'country': 'Thailand', 'countryZh': '泰国', 'countryId': 'Thailand', 'countryVi': 'Thái Lan', 'visaType': 'tourism', 'status': 'approved', 'amount': 299.00, 'createdAt': '2026-06-01T10:00:00Z'},
    {'id': 'ORD-20260605-002', 'country': 'Vietnam', 'countryZh': '越南', 'countryId': 'Vietnam', 'countryVi': 'Việt Nam', 'visaType': 'tourism', 'status': 'paid', 'amount': 199.00, 'createdAt': '2026-06-05T14:30:00Z'},
    {'id': 'ORD-20260610-003', 'country': 'Indonesia', 'countryZh': '印度尼西亚', 'countryId': 'Indonesia', 'countryVi': 'Indonesia', 'visaType': 'tourism', 'status': 'pending_payment', 'amount': 199.00, 'createdAt': '2026-06-10T09:15:00Z'},
    {'id': 'ORD-20260608-004', 'country': 'Thailand', 'countryZh': '泰国', 'countryId': 'Thailand', 'countryVi': 'Thái Lan', 'visaType': 'student', 'status': 'rejected', 'amount': 599.00, 'createdAt': '2026-06-08T11:20:00Z', 'rejectReason': '材料不完整，请补充护照扫描件'},
    {'id': 'ORD-20260611-005', 'country': 'Philippines', 'countryZh': '菲律宾', 'countryId': 'Filipina', 'countryVi': 'Philippines', 'visaType': 'tourism', 'status': 'reviewing', 'amount': 199.00, 'createdAt': '2026-06-11T16:45:00Z'},
  ];

  List<Map<String, dynamic>> get _filteredOrders {
    if (_activeTab == 'all') return _allOrders;
    return _allOrders.where((o) => o['status'] == _activeTab).toList();
  }

  String _countryName(Map<String, dynamic> o) {
    final l = AppLocalizations.of(context)!;
    final code = l.localeName;
    if (code.startsWith('zh')) return o['countryZh'] as String;
    if (code == 'id') return o['countryId'] as String;
    if (code == 'vi') return o['countryVi'] as String;
    return o['country'] as String;
  }

  String _visaType(Map<String, dynamic> o) {
    final l = AppLocalizations.of(context)!;
    return o['visaType'] == 'student' ? l.orderItemVisaStudent : l.orderItemVisaTourism;
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'approved': return const Color(0xFF10B981);
      case 'rejected': return const Color(0xFFEF4444);
      case 'pending_payment': return const Color(0xFFF59E0B);
      case 'paid': return const Color(0xFF3B6EF5);
      case 'reviewing': return const Color(0xFF8B5CF6);
      default: return Colors.grey;
    }
  }

  String _statusLabel(AppLocalizations l, String status) {
    switch (status) {
      case 'approved': return l.orderTabApproved;
      case 'rejected': return l.orderTabRejected;
      case 'pending_payment': return l.orderTabPendingPayment;
      case 'paid': return l.orderTabPaid;
      case 'reviewing': return l.orderTabReviewing;
      default: return status;
    }
  }

  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  void _checkAuth() {
    // For demo: always show logged-in state with mock data
    setState(() { _isLoggedIn = true; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)), onPressed: () => Navigator.pop(context)),
        title: Text(l.orderPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: !_isLoggedIn
            ? _buildNotLoggedIn(l)
            : Column(
                children: [
                  _buildTabBar(l),
                  Expanded(child: _buildList(l)),
                ],
              ),
      ),
    );
  }

  Widget _buildNotLoggedIn(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_outline, size: 48, color: Color(0xFF9CA3AF)),
            const SizedBox(height: 16),
            Text(l.orderNotLoggedIn, style: const TextStyle(fontSize: 16, color: Color(0xFF6B7280))),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => Navigator.pushNamed(context, AppRoutes.login),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B6EF5),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
              child: Text(l.orderGoLogin),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTabBar(AppLocalizations l) {
    return Container(
      color: Colors.white,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: _tabs.map((tab) {
            final active = tab.key == _activeTab;
            return Padding(
              padding: const EdgeInsets.only(right: 6),
              child: FilterChip(
                label: Text(_tabLabel(l, tab.key), style: TextStyle(fontSize: 13, color: active ? Colors.white : const Color(0xFF6B7280))),
                selected: active,
                onSelected: (_) => setState(() => _activeTab = tab.key),
                backgroundColor: Colors.white,
                selectedColor: const Color(0xFF3B6EF5),
                checkmarkColor: Colors.white,
                side: BorderSide(color: active ? const Color(0xFF3B6EF5) : const Color(0xFFE5E7EB)),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                padding: const EdgeInsets.symmetric(horizontal: 8),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  String _tabLabel(AppLocalizations l, String key) {
    switch (key) {
      case 'all': return l.orderTabAll;
      case 'pending_payment': return l.orderTabPendingPayment;
      case 'paid': return l.orderTabPaid;
      case 'reviewing': return l.orderTabReviewing;
      case 'approved': return l.orderTabApproved;
      case 'rejected': return l.orderTabRejected;
      default: return key;
    }
  }

  Widget _buildList(AppLocalizations l) {
    final orders = _filteredOrders;
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (orders.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.inbox_outlined, size: 48, color: Color(0xFF9CA3AF)),
              const SizedBox(height: 12),
              Text(l.orderEmptyTitle, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF6B7280))),
              const SizedBox(height: 4),
              Text(l.orderEmptyDesc, style: const TextStyle(fontSize: 14, color: Color(0xFF9CA3AF))),
            ],
          ),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: () async => setState(() {}),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: orders.length,
        itemBuilder: (ctx, i) => _OrderCard(
          order: orders[i],
          l: l,
          countryName: _countryName(orders[i]),
          visaType: _visaType(orders[i]),
          statusColor: _statusColor(orders[i]['status'] as String),
          statusLabel: _statusLabel(l, orders[i]['status'] as String),
          onPay: () => Navigator.pushNamed(context, AppRoutes.payment, arguments: orders[i]['id']),
          onViewDetail: () => Navigator.pushNamed(context, AppRoutes.orderDetail, arguments: orders[i]['id']),
        ),
      ),
    );
  }
}

class _OrderTab {
  final String key;
  final String labelKey;
  const _OrderTab({required this.key, required this.labelKey});
}

class _OrderCard extends StatelessWidget {
  final Map<String, dynamic> order;
  final AppLocalizations l;
  final String countryName;
  final String visaType;
  final Color statusColor;
  final String statusLabel;
  final VoidCallback onPay;
  final VoidCallback onViewDetail;

  const _OrderCard({
    required this.order, required this.l, required this.countryName,
    required this.visaType, required this.statusColor, required this.statusLabel,
    required this.onPay, required this.onViewDetail,
  });

  @override
  Widget build(BuildContext context) {
    final amount = (order['amount'] as num).toDouble();
    final status = order['status'] as String;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(order['id'] as String, style: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
                child: Text(statusLabel, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: statusColor)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text('$countryName — $visaType', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 4),
          Text('¥${amount.toStringAsFixed(2)} · ${order['createdAt'].toString().substring(0, 10)}', style: const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
          if (status == 'rejected' && order['rejectReason'] != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: const Color(0xFFFEF2F2), borderRadius: BorderRadius.circular(8)),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 16, color: Color(0xFFEF4444)),
                  const SizedBox(width: 6),
                  Expanded(child: Text('${l.orderRejectReasonLabel}: ${order['rejectReason']}', style: const TextStyle(fontSize: 12, color: Color(0xFFEF4444)))),
                ],
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              if (status == 'pending_payment')
                Expanded(
                  child: ElevatedButton(
                    onPressed: onPay,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFF59E0B),
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    child: Text(l.orderItemPayNow, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                  ),
                )
              else
                Expanded(
                  child: OutlinedButton(
                    onPressed: onViewDetail,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF3B6EF5),
                      side: const BorderSide(color: Color(0xFF3B6EF5)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    child: Text(l.orderItemViewDetail, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}