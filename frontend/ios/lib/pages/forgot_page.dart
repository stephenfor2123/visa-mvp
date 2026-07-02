// Forgot password page — W32 port. Uses account (email OR username).
//
// Step 1: enter account → Step 2: set new password → POST /api/v2/auth/reset-password
// No SMS required in W32 schema.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

class ForgotPage extends StatefulWidget {
  const ForgotPage({super.key});

  @override
  State<ForgotPage> createState() => _ForgotPageState();
}

class _ForgotPageState extends State<ForgotPage> {
  final _accountCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  bool _submitting = false;
  bool _success = false;

  Map<String, String> _errors = {};

  @override
  void dispose() {
    _accountCtrl.dispose();
    _pwdCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _onSubmit() async {
    final acc = _accountCtrl.text.trim();
    final pwd = _pwdCtrl.text;
    final confirm = _confirmCtrl.text;

    Map<String, String> errors = {};
    if (acc.isEmpty) errors['account'] = '请输入邮箱或用户名';
    if (pwd.length < 8) errors['newPwd'] = '密码至少 8 位';
    if (confirm != pwd) errors['confirmPwd'] = '两次密码不一致';

    if (errors.isNotEmpty) {
      setState(() => _errors = errors);
      return;
    }

    setState(() {
      _submitting = true;
      _errors = {};
    });
    try {
      final svc = AuthService();
      await svc.resetPassword(account: acc, newPassword: pwd);
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _success = true;
      });
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _errors = {'account': e.message};
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _errors = {'account': e.toString()};
      });
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
        leading: IconButton(icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)), onPressed: () => Navigator.pop(context)),
        title: Text(l.forgotPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: _success ? _buildSuccess(l) : SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l.forgotPageSubtitle, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            const SizedBox(height: 24),
            _buildLabel('账号'),
            _buildTextField(
              controller: _accountCtrl,
              placeholder: 'user@example.com 或 username',
              prefixIcon: Icons.person_outline,
              error: _errors['account'],
            ),
            const SizedBox(height: 16),
            _buildLabel(l.forgotNewPwdLabel),
            _buildTextField(
              controller: _pwdCtrl,
              placeholder: l.forgotNewPwdPlaceholder,
              obscure: true,
              prefixIcon: Icons.lock_outline,
              error: _errors['newPwd'],
            ),
            const SizedBox(height: 16),
            _buildLabel(l.forgotConfirmPwdLabel),
            _buildTextField(
              controller: _confirmCtrl,
              placeholder: l.forgotConfirmPwdPlaceholder,
              obscure: true,
              prefixIcon: Icons.lock_outline,
              error: _errors['confirmPwd'],
            ),
            const SizedBox(height: 28),
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
          ]),
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
    IconData? prefixIcon,
    String? error,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      TextField(
        controller: controller,
        obscureText: obscure,
        keyboardType: keyboardType,
        decoration: InputDecoration(
          hintText: placeholder,
          hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
          prefixIcon: prefixIcon != null ? Icon(prefixIcon, size: 18, color: const Color(0xFF94A3B8)) : null,
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
    ]);
  }

  Widget _buildSuccess(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
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
        ]),
      ),
    );
  }
}