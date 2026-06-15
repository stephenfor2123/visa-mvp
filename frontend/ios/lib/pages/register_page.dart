// Register page — port of frontend/web/src/views/Register.vue to Flutter (W8-1).
//
// Form layout mirrors the web register page on mobile:
// - Phone (with country code prefix) + SMS code (with 60s send button cooldown)
// - Password + Confirm password with live strength meter (weak/medium/strong)
// - Agreement checkbox + Terms/Privacy links
// - Submit button + "go to login" link
//
// Submit posts to backend /api/v2/auth/register (added in W6b).
// SMS send posts to /api/v2/auth/send-code (added in W6-1).

import 'dart:async';
import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _phoneCtrl = TextEditingController();
  final _smsCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  String _countryCode = '+86';
  bool _agreed = false;
  bool _submitting = false;
  bool _sending = false;
  int _smsCooldown = 0;
  Timer? _cooldownTimer;

  String? _phoneErr;
  String? _smsErr;
  String? _pwdErr;
  String? _confirmErr;
  String? _generalErr;

  static final RegExp _pwdRe = RegExp(
    r'^(?=.*[A-Za-z])(?=.*\d)[\w!@#$%^&*()+\-=\[\]{};|\\,.<>/?`~]{8,32}$',
  );

  @override
  void initState() {
    super.initState();
    _pwdCtrl.addListener(_onPwdChanged);
  }

  @override
  void dispose() {
    _cooldownTimer?.cancel();
    _phoneCtrl.dispose();
    _smsCtrl.dispose();
    _pwdCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  void _onPwdChanged() {
    // Trigger a rebuild to refresh the live strength hint.
    setState(() {});
  }

  // Returns 0=empty, 1=weak, 2=medium, 3=strong.
  int _pwdStrength() {
    final v = _pwdCtrl.text;
    if (v.isEmpty) return 0;
    if (v.length < 8) return 1;
    if (v.length > 32) return 1;
    final hasLetter = RegExp('[A-Za-z]').hasMatch(v);
    final hasDigit = RegExp(r'\d').hasMatch(v);
    final hasSymbol = RegExp(r'[!@#$%^&*()_+\-=\[\]{}|\\,.<>/?`~]')
        .hasMatch(v);
    int score = 0;
    if (hasLetter) score++;
    if (hasDigit) score++;
    if (hasSymbol) score++;
    if (v.length >= 12) score++;
    if (score >= 3) return 3;
    if (score >= 2) return 2;
    return 1;
  }

  String? _pwdHintText(AppLocalizations l) {
    final v = _pwdCtrl.text;
    if (v.isEmpty) return null;
    if (v.length < 8) return l.registerPwdHintShort;
    if (v.length > 32) return l.registerPwdHintLong;
    if (!_pwdRe.hasMatch(v)) return l.registerPwdHintFormat;
    if (_confirmCtrl.text.isNotEmpty && _pwdCtrl.text != _confirmCtrl.text) {
      return l.registerPwdHintMismatch;
    }
    return l.registerPwdHintOk;
  }

  String _pwdStrengthLabel(AppLocalizations l) {
    switch (_pwdStrength()) {
      case 1:
        return l.registerPwdStrengthWeak;
      case 2:
        return l.registerPwdStrengthMedium;
      case 3:
        return l.registerPwdStrengthStrong;
      default:
        return '';
    }
  }

  Color _pwdStrengthColor() {
    switch (_pwdStrength()) {
      case 1:
        return const Color(0xFFDC2626);
      case 2:
        return const Color(0xFFD97706);
      case 3:
        return const Color(0xFF16A34A);
      default:
        return const Color(0xFFCBD5E1);
    }
  }

  bool _validateAll(AppLocalizations l) {
    setState(() {
      _phoneErr = null;
      _smsErr = null;
      _pwdErr = null;
      _confirmErr = null;
    });
    var ok = true;
    if (_phoneCtrl.text.trim().length < 5) {
      _phoneErr = l.errorsPhoneInvalid;
      ok = false;
    }
    if (!RegExp(r'^\d{6}$').hasMatch(_smsCtrl.text)) {
      _smsErr = l.errorsCodeInvalid;
      ok = false;
    }
    if (!_pwdRe.hasMatch(_pwdCtrl.text)) {
      _pwdErr = l.registerPwdHintFormat;
      ok = false;
    }
    if (_pwdCtrl.text != _confirmCtrl.text) {
      _confirmErr = l.registerPwdHintMismatch;
      ok = false;
    }
    if (!_agreed) {
      _generalErr = l.errorsAgreement;
      ok = false;
    }
    return ok;
  }

  Future<void> _onSendCode(AppLocalizations l) async {
    if (_smsCooldown > 0 || _sending) return;
    if (_phoneCtrl.text.trim().length < 5) {
      setState(() => _phoneErr = l.errorsPhoneInvalid);
      return;
    }
    setState(() => _sending = true);
    try {
      final svc = AuthService();
      final code = await svc.sendCode(
        phone: _phoneCtrl.text.trim(),
        phoneCountry: _countryCode,
        purpose: 'register',
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${l.toastCodeSendSuccess} ($code)')),
      );
      setState(() {
        _smsCooldown = 60;
      });
      _cooldownTimer?.cancel();
      _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!mounted) {
          t.cancel();
          return;
        }
        setState(() {
          _smsCooldown -= 1;
          if (_smsCooldown <= 0) {
            t.cancel();
          }
        });
      });
    } on AuthException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${e.code}: ${e.message}')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.errorsNetwork)),
      );
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _onSubmit(AppLocalizations l) async {
    if (!_validateAll(l)) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      await svc.register(
        phone: _phoneCtrl.text.trim(),
        phoneCountry: _countryCode,
        password: _pwdCtrl.text,
        smsCode: _smsCtrl.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.toastRegisterSuccess)),
      );
      Navigator.of(context).pushReplacementNamed(AppRoutes.login);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = '${e.code}: ${e.message}');
    } catch (_) {
      if (!mounted) return;
      setState(() => _generalErr = l.errorsNetwork);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: Text(l.navRegister),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                elevation: 1,
                color: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        l.registerTitle,
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        l.registerSubtitle,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 18),
                      _buildPhoneField(l, theme),
                      const SizedBox(height: 12),
                      _buildSmsField(l, theme),
                      const SizedBox(height: 12),
                      _buildPwdField(l, theme),
                      if (_pwdCtrl.text.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        _buildStrengthMeter(theme),
                      ],
                      const SizedBox(height: 12),
                      _buildConfirmField(l, theme),
                      const SizedBox(height: 12),
                      _buildAgreement(l, theme),
                      if (_generalErr != null) ...[
                        const SizedBox(height: 6),
                        Text(
                          _generalErr!,
                          style: TextStyle(
                            color: theme.colorScheme.error,
                            fontSize: 12,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: _submitting ? null : () => _onSubmit(l),
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
                            : Text(
                                l.registerSubmit,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w600),
                              ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            l.registerHaveAccount,
                            style: const TextStyle(
                                fontSize: 13, color: Color(0xFF64748B)),
                          ),
                          TextButton(
                            onPressed: _submitting
                                ? null
                                : () => Navigator.of(context)
                                    .pushReplacementNamed(AppRoutes.login),
                            child: Text(l.registerGoLogin),
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
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(
            '© 2026 ${l.appName} · W8 demo',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF)),
          ),
        ),
      ),
    );
  }

  Widget _buildPhoneField(AppLocalizations l, ThemeData theme) {
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
              labelText: l.registerPhoneLabel,
              hintText: l.registerPhonePlaceholder,
              errorText: _phoneErr,
              border: const OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSmsField(AppLocalizations l, ThemeData theme) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: TextField(
            controller: _smsCtrl,
            keyboardType: TextInputType.number,
            maxLength: 6,
            decoration: InputDecoration(
              labelText: l.registerSmsLabel,
              hintText: l.registerSmsPlaceholder,
              errorText: _smsErr,
              counterText: '',
              border: const OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 110,
          child: OutlinedButton(
            onPressed: (_smsCooldown > 0 || _sending)
                ? null
                : () => _onSendCode(l),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _sending
                ? const SizedBox(
                    height: 14,
                    width: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(
                    _smsCooldown > 0
                        ? '${_smsCooldown}s'
                        : l.registerSendCode,
                    style: const TextStyle(fontSize: 12),
                  ),
          ),
        ),
      ],
    );
  }

  Widget _buildPwdField(AppLocalizations l, ThemeData theme) {
    return TextField(
      controller: _pwdCtrl,
      obscureText: true,
      maxLength: 32,
      decoration: InputDecoration(
        labelText: l.registerPwdLabel,
        hintText: l.registerPwdPlaceholder,
        errorText: _pwdErr,
        helperText: _pwdHintText(l),
        counterText: '',
        border: const OutlineInputBorder(),
        isDense: true,
      ),
    );
  }

  Widget _buildStrengthMeter(ThemeData theme) {
    final strength = _pwdStrength();
    return Row(
      children: [
        Expanded(
          flex: 1,
          child: Container(
            height: 4,
            decoration: BoxDecoration(
              color: strength >= 1
                  ? _pwdStrengthColor()
                  : const Color(0xFFE2E8F0),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
        const SizedBox(width: 4),
        Expanded(
          flex: 1,
          child: Container(
            height: 4,
            decoration: BoxDecoration(
              color: strength >= 2
                  ? _pwdStrengthColor()
                  : const Color(0xFFE2E8F0),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
        const SizedBox(width: 4),
        Expanded(
          flex: 1,
          child: Container(
            height: 4,
            decoration: BoxDecoration(
              color: strength >= 3
                  ? _pwdStrengthColor()
                  : const Color(0xFFE2E8F0),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 50,
          child: Text(
            _pwdStrengthLabel(AppLocalizations.of(context)),
            style: TextStyle(
              fontSize: 11,
              color: _pwdStrengthColor(),
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildConfirmField(AppLocalizations l, ThemeData theme) {
    return TextField(
      controller: _confirmCtrl,
      obscureText: true,
      maxLength: 32,
      onChanged: (_) => setState(() {}),
      decoration: InputDecoration(
        labelText: l.registerConfirmLabel,
        hintText: l.registerConfirmPlaceholder,
        errorText: _confirmErr,
        counterText: '',
        border: const OutlineInputBorder(),
        isDense: true,
      ),
    );
  }

  Widget _buildAgreement(AppLocalizations l, ThemeData theme) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Checkbox(
          value: _agreed,
          onChanged: (v) => setState(() => _agreed = v ?? false),
          visualDensity: VisualDensity.compact,
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Wrap(
              children: [
                Text(
                  l.registerAgreementPrefix + ' ',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                ),
                Text(
                  l.registerAgreementTerms,
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.primary,
                    decoration: TextDecoration.underline,
                  ),
                ),
                Text(
                  ' ' + l.registerAgreementAnd + ' ',
                  style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
                ),
                Text(
                  l.registerAgreementPrivacy,
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.primary,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
