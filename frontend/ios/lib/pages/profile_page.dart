// Profile page — W13 Flutter iOS port of miniprogram/pages/profile/.
//
// Shows user info card (avatar initial + phone + member since).
// Unauthenticated state shows login CTA.
// Authenticated state shows profile + nav actions: My Orders / Forgot Password / Agreement / Logout.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  AuthUser? _user;
  bool _isLoggedIn = false;
  String _registerTime = '-';
  String _initial = '?';
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadUser();
  }

  Future<void> _loadUser() async {
    final user = await AuthService.loadUserAsync();
    final loggedIn = await AuthService.isLoggedIn();
    setState(() {
      _user = user;
      _isLoggedIn = loggedIn;
      _loading = false;
      if (user != null) {
        _registerTime = user['createdAt'] != null
            ? _formatDate(user['createdAt'])
            : '-';
        final name = user['nickname'] ?? user['phone'] ?? '?';
        _initial = name.isNotEmpty ? name[0].toUpperCase() : '?';
      } else {
        _registerTime = '-';
        _initial = '?';
      }
    });
  }

  String _formatDate(String iso) {
    try {
      final d = DateTime.parse(iso);
      return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  void _onLogout() async {
    final l = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(l.navLogout),
        content: Text('${l.toastLogoutSuccess}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text(l.commonCancel)),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await AuthService.clearSession();
              _loadUser();
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(l.toastLogoutSuccess), backgroundColor: Colors.green),
                );
              }
            },
            child: Text(l.navLogout),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Text('htex', style: const TextStyle(color: Color(0xFF0F172A), fontWeight: FontWeight.w800, fontSize: 20, letterSpacing: -0.4)),
      ),
      body: SafeArea(
        child: _isLoggedIn ? _buildLoggedIn(l) : _buildLoggedOut(l),
      ),
    );
  }

  Widget _buildLoggedIn(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // User card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
            ),
            child: Column(
              children: [
                Container(
                  width: 64, height: 64,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [Color(0xFF3B6EF5), Color(0xFF6E59F0)]),
                    borderRadius: BorderRadius.circular(32),
                  ),
                  alignment: Alignment.center,
                  child: Text(_initial, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(height: 12),
                Text(_user?['nickname'] ?? _user?['phone'] ?? 'User', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
                const SizedBox(height: 4),
                if (_user?['phone'] != null)
                  Text('${_user!['phone']}', style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _infoChip(l.profileUserId, '#${_user?['id'] ?? '-'}'),
                    const SizedBox(width: 8),
                    _infoChip(l.profileRegisterTime, _registerTime),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Nav items
          _navTile(Icons.receipt_long, l.orderPageTitle, () => Navigator.pushNamed(context, AppRoutes.orders)),
          _navTile(Icons.language, l.profileLanguagePref, () => _showLanguageSheet(context)),
          _navTile(Icons.lock_reset, l.profileForgotPwd, () => Navigator.pushNamed(context, AppRoutes.forgot)),
          _navTile(Icons.description, l.profileAgreement, () => Navigator.pushNamed(context, AppRoutes.agreement)),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _onLogout,
              icon: const Icon(Icons.logout),
              label: Text(l.navLogout),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFEF2F2),
                foregroundColor: const Color(0xFFEF4444),
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoggedOut(AppLocalizations l) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80, height: 80,
              decoration: BoxDecoration(
                color: const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(40),
              ),
              child: const Icon(Icons.person_outline, size: 40, color: Color(0xFF3B6EF5)),
            ),
            const SizedBox(height: 20),
            Text(l.profilePageTitle, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
            const SizedBox(height: 8),
            Text(l.profilePageSubtitle, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, AppRoutes.login),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B6EF5),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: Text(l.profileGoLogin, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: const Color(0xFFEEF2FF), borderRadius: BorderRadius.circular(8)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF6B7280))),
          const SizedBox(width: 4),
          Text(value, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF3B6EF5))),
        ],
      ),
    );
  }

  Widget _navTile(IconData icon, String label, VoidCallback onTap) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 4, offset: const Offset(0, 1))],
      ),
      child: ListTile(
        leading: Icon(icon, color: const Color(0xFF3B6EF5)),
        title: Text(label, style: const TextStyle(fontSize: 15, color: Color(0xFF1A1A2E))),
        trailing: const Icon(Icons.chevron_right, color: Color(0xFF9CA3AF)),
        onTap: onTap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  void _showLanguageSheet(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    showModalBottomSheet(
      context: context,
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(title: Text(l.languageZh), onTap: () => Navigator.pop(context)),
          ListTile(title: Text(l.languageEn), onTap: () => Navigator.pop(context)),
          ListTile(title: Text(l.languageId), onTap: () => Navigator.pop(context)),
          ListTile(title: Text(l.languageVi), onTap: () => Navigator.pop(context)),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}