// OrderDetail page — W14 Flutter iOS port of web/src/views/OrderDetail.vue.
//
// Shows order status detail with 5-step timeline:
// Created → Submitted → Reviewing → Approved/Rejected.
// Mock data; real WS/polling integration in V2.1.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class OrderDetailPage extends StatefulWidget {
  final String? orderNo;
  OrderDetailPage({super.key, String? orderNo})
      : orderNo = orderNo ?? Uri.base.queryParameters['order_no'];

  @override
  State<OrderDetailPage> createState() => _OrderDetailPageState();
}

class _OrderDetailPageState extends State<OrderDetailPage> {
  bool _loading = true;
  String? _error;

  // Mock order — replace with AuthService / API call in V2.1
  Map<String, dynamic>? _order;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await Future.delayed(const Duration(milliseconds: 600));
    if (!mounted) return;
    setState(() {
      _order = {
        'order_no': widget.orderNo ?? 'ORD-20260610-003',
        'country': 'Indonesia',
        'countryZh': '印度尼西亚',
        'countryId': 'Indonesia',
        'countryVi': 'Indonesia',
        'visaType': 'tourism',
        'status': 'reviewing', // testing: try 'approved' / 'rejected' / 'paid'
        'amount': 199.00,
        'created_at': '2026-06-10T09:15:00Z',
        'updated_at': '2026-06-11T14:30:00Z',
        'reject_reason': null,
        'passport_name': 'SANTOSO BUDI',
        'passport_no': 'B12345678',
      };
      _loading = false;
    });
  }

  String _countryName() {
    final l = AppLocalizations.of(context)!;
    final code = l.localeName;
    if (code.startsWith('zh')) return _order!['countryZh'] as String;
    if (code == 'id') return _order!['countryId'] as String;
    if (code == 'vi') return _order!['countryVi'] as String;
    return _order!['country'] as String;
  }

  String _visaTypeLabel() {
    final l = AppLocalizations.of(context)!;
    return _order!['visaType'] == 'student' ? l.orderItemVisaStudent : l.orderItemVisaTourism;
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'approved': return const Color(0xFF10B981);
      case 'rejected': return const Color(0xFFEF4444);
      case 'pending_payment': return const Color(0xFFF59E0B);
      case 'paid': return const Color(0xFF3B6EF5);
      case 'reviewing': return const Color(0xFF8B5CF6);
      case 'submitted': return const Color(0xFF3B6EF5);
      default: return Colors.grey;
    }
  }

  String _statusLabel(String status) {
    final l = AppLocalizations.of(context)!;
    switch (status) {
      case 'approved': return l.orderTabApproved;
      case 'rejected': return l.orderTabRejected;
      case 'pending_payment': return l.orderTabPendingPayment;
      case 'paid': return l.orderTabPaid;
      case 'reviewing': return l.orderTabReviewing;
      default: return status;
    }
  }

  String _statusIcon(String status) {
    switch (status) {
      case 'approved': return '✅';
      case 'rejected': return '❌';
      case 'pending_payment': return '⏳';
      case 'paid': return '💳';
      case 'reviewing': return '🔍';
      case 'submitted': return '📤';
      default: return '⏸';
    }
  }

  // 5-step timeline states
  List<_TimelineStep> _steps(String status) {
    final l = AppLocalizations.of(context)!;
    return [
      _TimelineStep(key: 'created', label: l.orderdetailStepCreated, icon: Icons.receipt),
      _TimelineStep(key: 'submitted', label: l.orderdetailStepSubmitted, icon: Icons.send),
      _TimelineStep(key: 'reviewing', label: l.orderdetailStepReviewing, icon: Icons.pending),
      _TimelineStep(key: 'approved', label: l.orderdetailStepApproved, icon: Icons.check_circle),
      _TimelineStep(key: 'rejected', label: l.orderdetailStepRejected, icon: Icons.cancel),
    ];
  }

  int _stepIndex(String status) {
    switch (status) {
      case 'created': return 0;
      case 'submitted': return 1;
      case 'paid': return 1;
      case 'reviewing': return 2;
      case 'approved': return 3;
      case 'rejected': return 4;
      default: return 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(l.orderdetailPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: Color(0xFF3B6EF5)))
            : _error != null
                ? _buildError(l)
                : _buildContent(l),
      ),
    );
  }

  Widget _buildError(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Color(0xFFEF4444)),
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Color(0xFFEF4444))),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _load,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B6EF5),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: Text(l.commonRetry),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(AppLocalizations l) {
    final status = _order!['status'] as String;
    final color = _statusColor(status);
    final stepIndex = _stepIndex(status);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Hero card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.orderdetailOrderNoLabel, style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                const SizedBox(height: 4),
                Text(_order!['order_no'] as String, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
                const SizedBox(height: 4),
                Text('${_countryName()} · ${_visaTypeLabel()}', style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(_statusIcon(status), style: const TextStyle(fontSize: 14)),
                          const SizedBox(width: 6),
                          Text(_statusLabel(status), style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: color)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text('${l.orderdetailUpdatedAtLabel}: ${_order!['updated_at'].toString().substring(0, 16).replaceAll('T', ' ')}',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Timeline
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.orderdetailSectionTimeline, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
                const SizedBox(height: 16),
                ..._buildTimeline(l, status, stepIndex),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Rejection reason
          if (status == 'rejected' && _order!['reject_reason'] != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFECACA)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.info_outline, color: Color(0xFFEF4444), size: 18),
                      const SizedBox(width: 6),
                      Text(l.orderRejectReasonLabel, style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFFEF4444))),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(_order!['reject_reason'] as String, style: const TextStyle(fontSize: 14, color: Color(0xFF7F1D1D))),
                ],
              ),
            ),
          if (status == 'rejected') const SizedBox(height: 16),
          // Passport info
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.orderdetailSectionPassport, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
                const SizedBox(height: 12),
                _infoRow(l.orderdetailFieldName, _order!['passport_name'] as String? ?? '-'),
                _infoRow(l.orderdetailFieldPassportNo, _order!['passport_no'] as String? ?? '-'),
              ],
            ),
          ),
          const SizedBox(height: 24),
          // Action buttons
          if (status == 'pending_payment')
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, AppRoutes.payment, arguments: _order!['order_no']),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFF59E0B),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                ),
                child: Text(l.orderItemPayNow, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          if (status == 'rejected')
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, AppRoutes.orderForm, arguments: _order!['order_no']),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B6EF5),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                ),
                child: const Text('重新申请', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
        ],
      ),
    );
  }

  List<Widget> _buildTimeline(AppLocalizations l, String status, int currentStep) {
    final steps = _steps(status);
    final isRejected = status == 'rejected';
    final rejectedAt = isRejected ? 4 : currentStep;

    return [
      for (int i = 0; i < steps.length; i++)
        _TimelineRow(
          step: steps[i],
          isActive: i == currentStep,
          isDone: i < currentStep,
          isRejected: isRejected && i == 4,
          isLast: i == steps.length - 1,
          l: l,
        ),
    ];
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
          Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFF1A1A2E))),
        ],
      ),
    );
  }
}

class _TimelineStep {
  final String key;
  final String label;
  final IconData icon;
  const _TimelineStep({required this.key, required this.label, required this.icon});
}

class _TimelineRow extends StatelessWidget {
  final _TimelineStep step;
  final bool isActive;
  final bool isDone;
  final bool isRejected;
  final bool isLast;
  final AppLocalizations l;

  const _TimelineRow({
    required this.step, required this.isActive, required this.isDone,
    required this.isRejected, required this.isLast, required this.l,
  });

  Color get _color {
    if (isDone) return const Color(0xFF10B981);
    if (isActive) return const Color(0xFF3B6EF5);
    if (isRejected) return const Color(0xFFEF4444);
    return const Color(0xFFD1D5DB);
  }

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 36,
            child: Column(
              children: [
                Container(
                  width: 32, height: 32,
                  decoration: BoxDecoration(
                    color: _color,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(isDone ? Icons.check : (step.icon as dynamic), size: 16, color: Colors.white),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: isDone ? const Color(0xFF10B981) : const Color(0xFFE5E7EB),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 16),
              child: Text(step.label, style: TextStyle(
                fontSize: 14,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                color: isActive || isDone ? const Color(0xFF1A1A2E) : const Color(0xFF9CA3AF),
              )),
            ),
          ),
        ],
      ),
    );
  }
}