// Home page — port of frontend/web/src/views/Home.vue to Flutter (W8-1).
//
// Layout mirrors the web home page on a mobile canvas:
// - AppBar with brand mark (V) + app name + nav actions (Home/Profile/Login)
// - Hero section: gradient background, slogan, subtitle, two CTAs, country chip grid
// - Features section: 4 feature cards (材料清单/拒签险/模板库/Affiliate)
//
// Country chips here are static (no destination API on W8-1 yet) — the W2
// destinations list will replace this list with real data.

import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  // 4 country chips shown in the hero — W2 will source from /api/v2/destinations.
  static const List<Map<String, String>> _heroCountries = [
    {'code': 'TH', 'flag': '🇹🇭', 'name': 'Thailand'},
    {'code': 'VN', 'flag': '🇻🇳', 'name': 'Vietnam'},
    {'code': 'ID', 'flag': '🇮🇩', 'name': 'Indonesia'},
    {'code': 'PH', 'flag': '🇵🇭', 'name': 'Philippines'},
    {'code': 'MY', 'flag': '🇲🇾', 'name': 'Malaysia'},
    {'code': 'SG', 'flag': '🇸🇬', 'name': 'Singapore'},
  ];

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeader(context, l, theme),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _buildHero(context, l, theme),
              ),
              const SizedBox(height: 28),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _buildFeatures(context, l, theme),
              ),
              const SizedBox(height: 24),
              _buildFooter(l, theme),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, AppLocalizations l, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: Colors.white,
      child: Row(
        children: [
          // Brand mark — matches web V mark
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF3B6EF5), Color(0xFF6E59F0)],
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: const Text(
              'V',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              l.appName,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          TextButton(
            onPressed: () => _goHome(context),
            child: Text(
              l.navHome,
              style: TextStyle(
                color: theme.colorScheme.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          TextButton(
            onPressed: () => _goLogin(context),
            child: Text(l.navLogin),
          ),
        ],
      ),
    );
  }

  Widget _buildHero(BuildContext context, AppLocalizations l, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 28),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF3B6EF5), Color(0xFF6E59F0)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: const [
          BoxShadow(
            color: Color(0x403B6EF5),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.homeSlogan,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 28,
              fontWeight: FontWeight.w700,
              height: 1.2,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            l.homeSubtitle,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton(
                onPressed: () => _goLogin(context),
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF3B6EF5),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                child: Text(
                  l.homeCtaLogin,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              OutlinedButton(
                onPressed: () => _goMaterials(context),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Color(0x99FFFFFF)),
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                child: Text(l.homeCtaExplore),
              ),
            ],
          ),
          const SizedBox(height: 22),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 1.4,
            children: _heroCountries
                .map((c) => _buildCountryChip(c['flag']!, c['name']!))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildCountryChip(String flag, String name) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0x26FFFFFF),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x33FFFFFF), width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(flag, style: const TextStyle(fontSize: 22)),
          Text(
            name,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatures(BuildContext context, AppLocalizations l, ThemeData theme) {
    final features = [
      _FeatureItem(
        icon: Icons.fact_check_outlined,
        title: l.homeFeature1Title,
        desc: l.homeFeature1Desc,
        color: const Color(0xFF3B6EF5),
      ),
      _FeatureItem(
        icon: Icons.shield_outlined,
        title: l.homeFeature2Title,
        desc: l.homeFeature2Desc,
        color: const Color(0xFFDC2626),
      ),
      _FeatureItem(
        icon: Icons.description_outlined,
        title: l.homeFeature3Title,
        desc: l.homeFeature3Desc,
        color: const Color(0xFF6E59F0),
      ),
      _FeatureItem(
        icon: Icons.card_giftcard_outlined,
        title: l.homeFeature4Title,
        desc: l.homeFeature4Desc,
        color: const Color(0xFF16A34A),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.homeFeatureTitle,
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          l.homeFeatureSubtitle,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.95,
          children: features.map((f) => _buildFeatureCard(f, theme)).toList(),
        ),
      ],
    );
  }

  Widget _buildFeatureCard(_FeatureItem f, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: f.color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(f.icon, color: f.color, size: 20),
          ),
          const SizedBox(height: 10),
          Text(
            f.title,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 4),
          Expanded(
            child: Text(
              f.desc,
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF64748B),
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(AppLocalizations l, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: Text(
          '© 2026 ${l.appName} · W8 demo',
          style: const TextStyle(
            fontSize: 11,
            color: Color(0xFF9CA3AF),
          ),
        ),
      ),
    );
  }

  // Navigation helpers — use the named route table in main.dart so back-stack
  // and deep-link semantics stay consistent with the URL map.
  void _goHome(BuildContext context) {
    Navigator.of(context).pushNamedAndRemoveUntil(AppRoutes.home, (route) => false);
  }

  void _goLogin(BuildContext context) {
    Navigator.of(context).pushNamed(AppRoutes.login);
  }

  void _goMaterials(BuildContext context) {
    Navigator.of(context).pushNamed(AppRoutes.materials);
  }
}

class _FeatureItem {
  final IconData icon;
  final String title;
  final String desc;
  final Color color;
  const _FeatureItem({
    required this.icon,
    required this.title,
    required this.desc,
    required this.color,
  });
}
