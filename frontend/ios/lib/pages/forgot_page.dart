// Forgot password page — W13 Flutter iOS port of miniprogram/pages/forgot/.
//
// Step 1: Send SMS code → Step 2: Set new password.
// Country code picker + phone input + SMS code + password fields.

import 'dart:async';
import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class ForgotPage extends StatefulWidget {
  const ForgotPage({super.key});

  @override
  State<ForgotPage> createState() => _ForgotPageState();
}

class _ForgotPageState extends State<ForgotPage> {
  int _countryIdx = 0;
  final List<Map<String, String>> _countries = [
    {'code': '+86', 'flag': '🇨🇳'},
    {'code': '+62', 'flag': '🇮🇩'},
    {'code': '+84', 'flag': '🇻🇳'},
    {'code': '+63', 'flag': '🇵🇭'},
  ];

  final _phoneCtrl = TextEditingController();
  final _smsCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  bool _sending = false;
  int _smsCooldown = 0;
  bool _submitting = false;
  bool _success = false;
  Timer? _cooldownTimer;

  Map<String, String> _errors = {};

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _smsCtrl.dispose();
    _pwdCtrl.dispose();
    _confirmCtrl.dispose();
    _cooldownTimer?.cancel();
    super.dispose();
  }

  void _onSendCode() {
    final l = AppLocalizations.of(context)!;
    final phone = _phoneCtrl.text.trim();
    if (phone.length < 5) {
      setState(() => _errors = {..._errors, 'phone': l.errorsPhoneInvalid});
      return;
    }
    setState(() { _sending = true; _errors = {..._errors, 'phone': ''}; });
    // Mock: SMS sent after 1s
    Future.delayed(const Duration(seconds: 1), () {
      if (!mounted) return;
      setState(() { _sending = false; _smsCooldown = 60; });
      _startCooldown();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('验证码已发送 (mock)'), backgroundColor: Colors.green),
      );
    });
  }

  void _startCooldown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() {
        if (_smsCooldown > 0) _smsCooldown--;
      });
      if (_smsCooldown == 0) _cooldownTimer?.cancel();
    });
  }

  void _onSubmit() {
    final l = AppLocalizations.of(context)!;
    final phone = _phoneCtrl.text.trim();
    final sms = _smsCtrl.text.trim();
    final pwd = _pwdCtrl.text;
    final confirm = _confirmCtrl.text;

    Map<String, String> errors = {};
    if (phone.length < 5) errors['phone'] = l.errorsPhoneInvalid;
    if (sms.length != 6) errors['smsCode'] = l.errorsCodeInvalid;
    if (pwd.length < 8) errors['newPwd'] = l.errorsPwdTooShort;
    if (confirm != pwd) errors['confirmPwd'] = l.errorsPwdMismatch;

    if (errors.isNotEmpty) {
      setState(() => _errors = errors);
      return;
    }

    setState(() { _submitting = true; _errors = {}; });
    // Mock: reset after 1.2s
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (!mounted) return;
      setState(() { _submitting = false; _success = true; });
    });
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
        title: Text(l.forgotPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: _success ? _buildSuccess(l) : SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l.forgotPageSubtitle, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
              const SizedBox(height: 24),
              // Country + Phone
              _buildLabel(l.forgotPhoneLabel),
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF3F4F6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: const Color(0xFFE5E7EB)),
                    ),
                    child: DropdownButton<int>(
                      value: _countryIdx,
                      underline: const SizedBox(),
                      items: _countries.asMap().entries.map((e) => DropdownMenuItem(
                        value: e.key,
                        child: Text('${e.value['flag']} ${e.value['code']}'),
                      )).toList(),
                      onChanged: (v) => setState(() => _countryIdx = v ?? 0),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildTextField(
                      controller: _phoneCtrl,
                      placeholder: l.forgotPhonePlaceholder,
                      keyboardType: TextInputType.phone,
                      error: _errors['phone'],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // SMS code
              _buildLabel(l.forgotSmsLabel),
              Row(
                children: [
                  Expanded(
                    child: _buildTextField(
                      controller: _smsCtrl,
                      placeholder: l.forgotSmsPlaceholder,
                      keyboardType: TextInputType.number,
                      error: _errors['smsCode'],
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    width: 120,
                    child: ElevatedButton(
                      onPressed: _smsCooldown > 0 || _sending ? null : _onSendCode,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFEEF2FF),
                        foregroundColor: const Color(0xFF3B6EF5),
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      child: Text(
                        _smsCooldown > 0 ? '${_smsCooldown}s' : l.forgotSendCode,
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // New password
              _buildLabel(l.forgotNewPwdLabel),
              _buildTextField(
                controller: _pwdCtrl,
                placeholder: l.forgotNewPwdPlaceholder,
                obscure: true,
                error: _errors['newPwd'],
              ),
              const SizedBox(height: 16),
              // Confirm password
              _buildLabel(l.forgotConfirmPwdLabel),
              _buildTextField(
                controller: _confirmCtrl,
                placeholder: l.forgotConfirmPwdPlaceholder,
                obscure: true,
                error: _errors['confirmPwd'],
              ),
              const SizedBox(height: 28),
              // Submit
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _submitting ? null : _onSubmit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF3B6EF5),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(vertical: 15),
                  ),
                  child: _submitting
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(l.forgotSubmit, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                ),
              ),
              const SizedBox(height: 16),
              Center(
                child: TextButton(
                  onPressed: () => Navigator.pushReplacementNamed(context, AppRoutes.login),
                  child: Text(l.forgotBackLogin, style: const TextStyle(color: Color(0xFF3B6EF5), fontSize: 14)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(text, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFF374151))),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String placeholder,
    bool obscure = false,
    TextInputType? keyboardType,
    String? error,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: controller,
          obscureText: obscure,
          keyboardType: keyboardType,
          decoration: InputDecoration(
            hintText: placeholder,
            hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
            filled: true,
            fillColor: Colors.white,
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: error != null ? const Color(0xFFEF4444) : const Color(0xFFE5E7EB)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: error != null ? const Color(0xFFEF4444) : const Color(0xFFE5E7EB)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: Color(0xFF3B6EF5)),
            ),
          ),
        ),
        if (error != null) Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(error, style: const TextStyle(fontSize: 12, color: Color(0xFFEF4444))),
        ),
      ],
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
              decoration: BoxDecoration(color: const Color(0xFFECFDF5), borderRadius: BorderRadius.circular(40)),
              child: const Icon(Icons.check_circle, size: 48, color: Color(0xFF10B981)),
            ),
            const SizedBox(height: 20),
            Text(l.forgotSuccessTitle, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
            const SizedBox(height: 8),
            Text(l.forgotSuccessDesc, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => Navigator.pushNamedAndRemoveUntil(context, AppRoutes.login, (r) => false),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B6EF5),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              ),
              child: Text(l.forgotGoLogin, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }
}