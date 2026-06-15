// Login page — port of frontend/web/src/views/Login.vue to Flutter (W6b F1.7).
//
// Simplified to: phone + password + agreement + submit. SMS tab kept in the
// UI scaffold (tabs toggle) so i18n key parity stays complete, but the SMS
// submit endpoint reuses the same /api/v2/auth/login (grant_type=sms).
//
// Styling mirrors the web auth-card aesthetic on a mobile screen —
// vertical card with primary CTA, country selector prefix, agreement
// checkbox below the form.

import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> with SingleTickerProviderStateMixin {
  late final TabController _tabController =
      TabController(length: 2, vsync: this);

  final _phoneCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _smsCtrl = TextEditingController();

  String _countryCode = '+86';
  bool _agreement = false;
  bool _remember = true;
  bool _submitting = false;

  String? _phoneErr;
  String? _pwdErr;
  String? _smsErr;
  String? _generalErr;

  @override
  void dispose() {
    _tabController.dispose();
    _phoneCtrl.dispose();
    _pwdCtrl.dispose();
    _smsCtrl.dispose();
    super.dispose();
  }

  bool _validatePwd(AppLocalizations l) {
    setState(() {
      _phoneErr = null;
      _pwdErr = null;
    });
    final phone = _phoneCtrl.text.trim();
    final pwd = _pwdCtrl.text;
    if (phone.length < 5) {
      _phoneErr = l.errorsPhoneInvalid;
      return false;
    }
    if (pwd.length < 6) {
      _pwdErr = l.errorsPwdTooShort;
      return false;
    }
    return true;
  }

  bool _validateSms(AppLocalizations l) {
    setState(() {
      _phoneErr = null;
      _smsErr = null;
    });
    final phone = _phoneCtrl.text.trim();
    final code = _smsCtrl.text.trim();
    if (phone.length < 5) {
      _phoneErr = l.errorsPhoneInvalid;
      return false;
    }
    if (!RegExp(r'^\d{6}$').hasMatch(code)) {
      _smsErr = l.errorsCodeInvalid;
      return false;
    }
    return true;
  }

  Future<void> _onPwdSubmit(AppLocalizations l) async {
    if (!_agreement) {
      setState(() => _generalErr = '⚠ ' + l.loginAgreementPrefix);
      return;
    }
    if (!_validatePwd(l)) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      final result = await svc.loginByPassword(
        phone: _phoneCtrl.text.trim(),
        phoneCountry: _countryCode,
        password: _pwdCtrl.text,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.toastLoginSuccess)),
      );
      debugPrint('login ok uid=${result.userId}');
      // W8-1: jump to home after a successful login.
      Navigator.of(context).pushNamedAndRemoveUntil(
        AppRoutes.home,
        (route) => false,
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = '${e.code}: ${e.message}');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.toastLoginFail)),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _onSmsSubmit(AppLocalizations l) async {
    if (!_agreement) {
      setState(() => _generalErr = '⚠ ' + l.loginAgreementPrefix);
      return;
    }
    if (!_validateSms(l)) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      final result = await svc.loginBySms(
        phone: _phoneCtrl.text.trim(),
        phoneCountry: _countryCode,
        code: _smsCtrl.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.toastLoginSuccess)),
      );
      debugPrint('sms login ok uid=${result.userId}');
      Navigator.of(context).pushNamedAndRemoveUntil(
        AppRoutes.home,
        (route) => false,
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = '${e.code}: ${e.message}');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(l.appName),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        l.loginTitle,
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        l.loginSubtitle,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 18),
                      TabBar(
                        controller: _tabController,
                        labelColor: theme.colorScheme.primary,
                        unselectedLabelColor: theme.colorScheme.onSurfaceVariant,
                        indicatorColor: theme.colorScheme.primary,
                        tabs: [
                          Tab(text: l.loginTabPwd),
                          Tab(text: l.loginTabSms),
                        ],
                      ),
                      const SizedBox(height: 18),
                      SizedBox(
                        height: 360,
                        child: TabBarView(
                          controller: _tabController,
                          children: [
                            _buildPwdForm(l, theme),
                            _buildSmsForm(l, theme),
                          ],
                        ),
                      ),
                      if (_generalErr != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          _generalErr!,
                          style: TextStyle(color: theme.colorScheme.error, fontSize: 12),
                          textAlign: TextAlign.center,
                        ),
                      ],
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Checkbox(
                            value: _agreement,
                            onChanged: (v) => setState(() => _agreement = v ?? false),
                          ),
                          Expanded(
                            child: Wrap(
                              children: [
                                Text(l.loginAgreementPrefix + ' '),
                                Text(
                                  l.loginAgreementTerms,
                                  style: TextStyle(color: theme.colorScheme.primary),
                                ),
                                Text(' ' + l.loginAgreementAnd + ' '),
                                Text(
                                  l.loginAgreementPrivacy,
                                  style: TextStyle(color: theme.colorScheme.primary),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            l.loginNoAccount,
                            style: const TextStyle(
                                fontSize: 13, color: Color(0xFF64748B)),
                          ),
                          TextButton(
                            onPressed: () =>
                                Navigator.of(context).pushNamed(AppRoutes.register),
                            child: Text(l.loginGoSignup),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPwdForm(AppLocalizations l, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _phoneField(l, theme),
        const SizedBox(height: 12),
        TextField(
          controller: _pwdCtrl,
          obscureText: true,
          decoration: InputDecoration(
            labelText: l.loginPwdLabel,
            hintText: l.loginPwdPlaceholder,
            errorText: _pwdErr,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Checkbox(
                  value: _remember,
                  onChanged: (v) => setState(() => _remember = v ?? false),
                ),
                Text(l.loginRemember, style: const TextStyle(fontSize: 12)),
              ],
            ),
            TextButton(
              onPressed: () {},
              child: Text(l.loginForgot),
            ),
          ],
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _submitting ? null : () => _onPwdSubmit(l),
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
          child: _submitting
              ? SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: theme.colorScheme.onPrimary,
                  ),
                )
              : Text(l.loginSubmit),
        ),
      ],
    );
  }

  Widget _buildSmsForm(AppLocalizations l, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _phoneField(l, theme),
        const SizedBox(height: 12),
        TextField(
          controller: _smsCtrl,
          keyboardType: TextInputType.number,
          maxLength: 6,
          decoration: InputDecoration(
            labelText: l.loginSmsLabel,
            hintText: l.loginSmsPlaceholder,
            errorText: _smsErr,
            counterText: '',
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: _submitting ? null : () {},
          style: OutlinedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 10),
          ),
          child: Text(l.loginSendCode),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _submitting ? null : () => _onSmsSubmit(l),
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
          child: _submitting
              ? SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: theme.colorScheme.onPrimary,
                  ),
                )
              : Text(l.loginSubmit),
        ),
      ],
    );
  }

  Widget _phoneField(AppLocalizations l, ThemeData theme) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            border: Border.all(color: theme.colorScheme.outline),
            borderRadius: BorderRadius.circular(4),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _countryCode,
              isDense: true,
              items: const [
                DropdownMenuItem(value: '+86', child: Text('+86 🇨🇳')),
                DropdownMenuItem(value: '+62', child: Text('+62 🇮🇩')),
                DropdownMenuItem(value: '+84', child: Text('+84 🇻🇳')),
                DropdownMenuItem(value: '+63', child: Text('+63 🇵🇭')),
              ],
              onChanged: (v) => setState(() => _countryCode = v ?? '+86'),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: TextField(
            controller: _phoneCtrl,
            keyboardType: TextInputType.phone,
            decoration: InputDecoration(
              labelText: l.loginPhoneLabel,
              hintText: l.loginPhonePlaceholder,
              errorText: _phoneErr,
              border: const OutlineInputBorder(),
            ),
          ),
        ),
      ],
    );
  }
}