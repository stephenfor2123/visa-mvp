// Payment page — W13 Flutter iOS port of miniprogram/pages/payment/.
//
// Shows WeChat QR code for payment with 15-minute countdown.
// 1.5s polling loop (mocked for demo; real API in V2.1).

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../l10n/generated/app_localizations.dart';

class PaymentPage extends StatefulWidget {
  final String? orderNo;
  const PaymentPage({super.key, this.orderNo});

  @override
  State<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends State<PaymentPage> {
  bool _loading = true;
  bool _paid = false;
  bool _failed = false;
  String _orderNo = '';
  String _codeUrl = '';
  double _amount = 299.0;
  int _countdownSec = 15 * 60; // 15 min
  int _pollCountdown = 0;
  Timer? _countdownTimer;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _orderNo = widget.orderNo ?? 'ORD-DEMO-001';
    _startPayment();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPayment() {
    setState(() {
      _loading = true;
      _paid = false;
      _failed = false;
      _countdownSec = 15 * 60;
    });
    // Mock: generate a fake code_url after 800ms
    Future.delayed(const Duration(milliseconds: 800), () {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _codeUrl = 'weixin://wxpay/bizpayurl?pr=PAYDEMO';
        _amount = 299.0;
        _startCountdown();
        _startPolling();
      });
    });
  }

  void _startCountdown() {
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() {
        if (_countdownSec > 0) _countdownSec--;
        if (_countdownSec == 0) _onExpired();
      });
    });
  }

  void _startPolling() {
    _pollTimer?.cancel();
    int pollCount = 0;
    _pollTimer = Timer.periodic(const Duration(milliseconds: 1500), (_) {
      if (!mounted || _paid || _failed) {
        _pollTimer?.cancel();
        return;
      }
      pollCount++;
      setState(() => _pollCountdown = pollCount);
      // Mock: auto-pay after ~10 polls for demo
      if (pollCount >= 10) {
        _pollTimer?.cancel();
        setState(() => _paid = true);
      }
    });
  }

  void _onExpired() {
    _pollTimer?.cancel();
    setState(() => _failed = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('二维码已过期，请重新生成'), backgroundColor: Colors.red),
    );
  }

  String _formatCountdown() {
    final m = (_countdownSec ~/ 60).toString().padLeft(2, '0');
    final s = (_countdownSec % 60).toString().padLeft(2, '0');
    return '$m:$s';
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
          onPressed: () => _showExitDialog(context, l),
        ),
        title: Text(l.paymentPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: _loading
            ? Center(child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const CircularProgressIndicator(color: Color(0xFF3B6EF5)),
                  const SizedBox(height: 16),
                  Text(l.paymentQrLoading, style: const TextStyle(color: Color(0xFF6B7280))),
                ],
              ))
            : _paid
                ? _buildSuccess(l)
                : _failed
                    ? _buildExpired(l)
                    : _buildQR(l),
      ),
    );
  }

  Widget _buildQR(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          // Amount card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8)],
            ),
            child: Column(
              children: [
                Text(l.paymentAmountLabel, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
                const SizedBox(height: 6),
                Text('¥${_amount.toStringAsFixed(2)}', style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(l.paymentOrderLabel + ': ', style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                    Text(_orderNo, style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          // QR code
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8)],
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    border: Border.all(color: const Color(0xFFE5E7EB)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: QrImageView(
                    data: _codeUrl,
                    version: QrVersions.auto,
                    size: 200,
                    backgroundColor: Colors.white,
                  ),
                ),
                const SizedBox(height: 12),
                Text(l.paymentQrHint, style: const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
              ],
            ),
          ),
          const SizedBox(height: 20),
          // Countdown
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
            decoration: BoxDecoration(
              color: _countdownSec < 120 ? const Color(0xFFFEF2F2) : const Color(0xFFEEF2FF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  _countdownSec < 120 ? Icons.timer_off : Icons.timer,
                  color: _countdownSec < 120 ? const Color(0xFFEF4444) : const Color(0xFF3B6EF5),
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  '${l.paymentExpireLabel}: ${_formatCountdown()}',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: _countdownSec < 120 ? const Color(0xFFEF4444) : const Color(0xFF3B6EF5),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '${l.paymentPollingLabel}: ${_pollCountdown} polls',
            style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
          ),
        ],
      ),
    );
  }

  Widget _buildSuccess(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80, height: 80,
              decoration: BoxDecoration(
                color: const Color(0xFFECFDF5),
                borderRadius: BorderRadius.circular(40),
              ),
              child: const Icon(Icons.check_circle, size: 48, color: Color(0xFF10B981)),
            ),
            const SizedBox(height: 20),
            Text(l.paymentStatusPaid, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
            const SizedBox(height: 8),
            Text(l.paymentBackSuccess, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => Navigator.pop(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B6EF5),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              ),
              child: const Text('返回首页', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExpired(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80, height: 80,
              decoration: BoxDecoration(
                color: const Color(0xFFFEF2F2),
                borderRadius: BorderRadius.circular(40),
              ),
              child: const Icon(Icons.error, size: 48, color: Color(0xFFEF4444)),
            ),
            const SizedBox(height: 20),
            Text(l.paymentQrExpired, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFFEF4444))),
            const SizedBox(height: 8),
            Text('请重新发起支付', style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: _startPayment,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B6EF5),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              ),
              child: const Text('重新生成二维码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }

  void _showExitDialog(BuildContext context, AppLocalizations l) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(l.paymentBackBtn),
        content: const Text('支付完成后可返回查看结果'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text(l.commonCancel)),
          ElevatedButton(
            onPressed: () { Navigator.pop(context); Navigator.pop(context); },
            child: const Text('确认退出'),
          ),
        ],
      ),
    );
  }
}