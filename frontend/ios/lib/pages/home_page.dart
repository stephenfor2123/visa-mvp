// Home page — W33 Atlys-style port of frontend/web/src/views/Home.vue.
//
// W33 update: 2-column compact country tiles + 10-photo hero slideshow.
//
// Key design points (Atlys-inspired):
//   - White background (not blue gradient)
//   - 2-column grid of compact country tiles: flag + name + FROM $X + chips
//   - 10-photo hero slideshow (matches PC web端) auto-rotates 6s
//   - Atlys "FROM $X" pricing transparency pattern
//   - White nav + clean type, mobile scroll-friendly

import 'dart:async';
import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../services/destinations_service.dart';
import 'apply_page.dart';
import 'diagnose_page.dart';
import 'resources_page.dart';
import 'contact_page.dart';
import 'passport_upload_page.dart';
import 'destinations_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List<Destination> _heroCountries = DestinationsService.fallback();
  List<Destination> _allCountries = DestinationsService.fallback();
  bool _loading = false;

  final _destSvc = DestinationsService();

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final lang = _activeLang();
    try {
      // W34: pass active locale so destination names come back translated
      // (e.g. zh → 美国, en → United States, id → Amerika Serikat).
      final list = await _destSvc.list(lang: lang);
      if (!mounted) return;
      final grouped = _destSvc.groupByVisaType(list);
      setState(() {
        _heroCountries = (grouped['national'] ?? []).isNotEmpty
            ? grouped['national']!
            : DestinationsService.fallback(lang: lang);
        _allCountries = list.isNotEmpty ? list : DestinationsService.fallback(lang: lang);
      });
    } catch (_) {
      // keep fallback (in active locale)
      if (!mounted) return;
      setState(() {
        final fb = DestinationsService.fallback(lang: lang);
        _heroCountries = fb;
        _allCountries = fb;
      });
    }
  }

  String _flagOf(String cc) {
    const flags = {'US': '🇺🇸', 'GB': '🇬🇧', 'AU': '🇦🇺', 'SCHENGEN': '🇪🇺', 'JP': '🇯🇵', 'KR': '🇰🇷', 'SG': '🇸🇬', 'FR': '🇫🇷'};
    return flags[cc] ?? '🌐';
  }

  // W33 country landmark photo asset (matches web端 Home.vue countryImage map).
  // Falls back to US landmark if the country isn't in the list.
  String _photoOf(String cc) {
    const map = {
      'US': 'assets/countries/us_liberty.jpg',
      'AU': 'assets/countries/au_sydney.jpg',
      'GB': 'assets/countries/gb_bigben.jpg',
      'SCHENGEN': 'assets/countries/schengen_eiffel.jpg',
    };
    return map[cc] ?? 'assets/countries/us_liberty.jpg';
  }

  // W34: short locale code (en / zh / id / vi) for API + fallback lookups.
  String _activeLang() {
    final l = AppLocalizations.of(context);
    final code = l?.localeName ?? 'zh';
    return code.split(RegExp('[-_]')).first.toLowerCase();
  }

  void _openApply(String? cc) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ApplyPage(initialCountryCode: cc)));
  }

  void _openDiagnose() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DiagnosePage()));
  void _openResources() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ResourcesPage()));
  void _openContact() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ContactPage()));
  void _openPassport() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PassportUploadPage()));
  void _openAllDestinations() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DestinationsPage()));

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            _buildHeader(context),
            const SizedBox(height: 8),
            _buildHeroBanner(context),
            const SizedBox(height: 20),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(l.homeHotVisa,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
                  TextButton(
                    onPressed: _openAllDestinations,
                    style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 0), tapTargetSize: MaterialTapTargetSize.shrinkWrap),
                    child: Text(l.homeViewAll, style: const TextStyle(fontSize: 12, color: Color(0xFF3B6EF5), fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            if (_loading)
              const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
            else
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                    childAspectRatio: 0.72,
                  ),
                  itemCount: _heroCountries.length,
                  itemBuilder: (_, i) => _buildCountryTile(_heroCountries[i]),
                ),
              ),
            const SizedBox(height: 20),
            _buildFeatures(context),
            const SizedBox(height: 24),
            _buildFooter(l),
          ],
        ),
      ),
    );
  }

  // ── Top nav ──────────────────────────────────────────────────────────────

  Widget _buildHeader(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      color: Colors.white,
      child: Row(
        children: [
          const Text(
            'htex',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: Color(0xFF0F172A),
              letterSpacing: -0.4,
            ),
          ),
          const Spacer(),
          IconButton(icon: const Icon(Icons.search, color: Color(0xFF64748B)), onPressed: _openAllDestinations),
          IconButton(icon: const Icon(Icons.person_outline, color: Color(0xFF64748B)), onPressed: () => Navigator.of(context).pushNamed('/login')),
        ],
      ),
    );
  }

  // ── Hero banner: 10-photo travel slideshow (matches web端 5173) ──────────

  // 10 张真实运动场景(雪山/海岛/极光/沙漠/星空/云海),每 6s 自动轮播。
  // Flutter Web build (8765) 不支持 mp4 自动循环,使用同名 jpg 静态图 +
  // AnimatedSwitcher 淡入淡出达到"动起来"的效果;真实 iOS App 端后续可
  // 换成 video_player 走 mp4。
  // t1 — 雪山 / 山野
  // t2 — 海岛 / 城市
  // t3 — 极光 / 天空
  // t4 — 沙漠 / 山系
  // t5 — 星空 / 云海
  static const List<String> _heroSlides = [
    'assets/hero/t1_snow.jpg',
    'assets/hero/t1_hiker.jpg',
    'assets/hero/t2_island.jpg',
    'assets/hero/t2_backpack_city.jpg',
    'assets/hero/t3_aurora.jpg',
    'assets/hero/t3_plane_sunset.jpg',
    'assets/hero/t4_desert.jpg',
    'assets/hero/t4_dolomites.jpg',
    'assets/hero/t5_stars.jpg',
    'assets/hero/t5_window_clouds.jpg',
  ];

  Widget _buildHeroBanner(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: SizedBox(
          height: 190,
          child: _HeroSlideshow(
            slides: _heroSlides,
            localePrefix: l?.homeHeroCityPrefix ?? '无限可能,随行而至',
            onDiagnose: _openDiagnose,
            onResources: _openResources,
          ),
        ),
      ),
    );
  }

  // ── 2-col compact country tile ──────────────────────────────────────────

  Widget _buildCountryTile(Destination d) {
    final l = AppLocalizations.of(context);
    final fromLabel = l?.homeFromPrice ?? 'FROM';
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => _openApply(d.countryCode),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // ── Full-bleed country photo ──
            Image.asset(
              _photoOf(d.countryCode),
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(
                color: const Color(0xFF1E3A8A),
                alignment: Alignment.center,
                child: Text(_flagOf(d.countryCode), style: const TextStyle(fontSize: 36)),
              ),
            ),
            // ── Bottom dark gradient (text legibility) ──
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Color(0x00000000),
                    Color(0x00000000),
                    Color(0x66000000),
                    Color(0xCC000000),
                  ],
                  stops: [0.0, 0.45, 0.75, 1.0],
                ),
              ),
            ),
            // ── Bottom: centered name + FROM $X + chips ──
            Positioned(
              left: 10, right: 10, bottom: 12,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    d.countryName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      shadows: _textShadow,
                    ),
                  ),
                  if (d.feeLabel.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(fromLabel, style: const TextStyle(fontSize: 9, color: Color(0xCCFFFFFF), fontWeight: FontWeight.w700, letterSpacing: 1.1, shadows: _textShadow)),
                        const SizedBox(width: 4),
                        Text(d.feeLabel, style: const TextStyle(fontSize: 17, color: Color(0xFFFBBF24), fontWeight: FontWeight.w800, shadows: _textShadow)),
                      ],
                    ),
                  ],
                  if (d.validityLabel.isNotEmpty || d.processLabel.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Wrap(
                      alignment: WrapAlignment.center,
                      spacing: 4,
                      runSpacing: 4,
                      children: [
                        if (d.validityLabel.isNotEmpty)
                          _miniChipOverlay(d.validityLabel, const Color(0xFF10B981)),
                        if (d.processLabel.isNotEmpty)
                          _miniChipOverlay(d.processLabel, const Color(0xFFF59E0B)),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // On-image chip: white-tinted background, full color text.
  Widget _miniChipOverlay(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: Colors.white.withOpacity(0.92), borderRadius: BorderRadius.circular(4)),
      child: Text(text, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w800, letterSpacing: 0.3)),
    );
  }

  Widget _miniChip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(4)),
      child: Text(text, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w700, letterSpacing: 0.3)),
    );
  }

  // ── Features ──────────────────────────────────────────────────────────────

  Widget _buildFeatures(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.homeSectionFeatures, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: _featureTile(Icons.upload_file_outlined, l.homeFeatureUploadTitle, l.homeFeatureUploadSub, const Color(0xFF3B6EF5), _openPassport)),
            const SizedBox(width: 10),
            Expanded(child: _featureTile(Icons.fact_check_outlined, l.homeFeatureDiagnoseTitle, l.homeFeatureDiagnoseSub, const Color(0xFF10B981), _openDiagnose)),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: _featureTile(Icons.menu_book_outlined, l.homeFeatureResourcesTitle, l.homeFeatureResourcesSub, const Color(0xFFF59E0B), _openResources)),
            const SizedBox(width: 10),
            Expanded(child: _featureTile(Icons.support_agent_outlined, l.homeFeatureContactTitle, l.homeFeatureContactSub, const Color(0xFFEF4444), _openContact)),
          ]),
        ],
      ),
    );
  }

  Widget _featureTile(IconData icon, String title, String sub, Color color, VoidCallback onTap) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(height: 10),
              Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
              const SizedBox(height: 2),
              Text(sub, style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFooter(AppLocalizations? l) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
      color: const Color(0xFFFAFBFC),
      child: Column(children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          _footerBtn(Icons.upload_file, l?.homeFooterUpload ?? '上传', _openPassport),
          _footerBtn(Icons.fact_check, l?.homeFooterDiagnose ?? '评估', _openDiagnose),
          _footerBtn(Icons.menu_book, l?.homeFooterQa ?? '问答', _openResources),
          _footerBtn(Icons.support_agent, l?.homeFooterContact ?? '客服', _openContact),
        ]),
        const SizedBox(height: 16),
        Text(l?.homeFooterCopyright ?? 'Htex · Wherever you go, life is infinite',
            style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
      ]),
    );
  }

  Widget _footerBtn(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Column(children: [
        Icon(icon, size: 22, color: const Color(0xFF64748B)),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
      ]),
    );
  }
}
// ─────────────────────────────────────────────────────────────────────────────
// _HeroSlideshow — auto-rotating carousel of product-aligned destinations.
// 5 verified destination photos (US/AU/GB/Schengen/FR). 6s cycle with crossfade.
// Matches web端 Home.vue slides[].city keys removed in W35 (i18n cleanup).
// ─────────────────────────────────────────────────────────────────────────────

class _HeroSlideshow extends StatefulWidget {
  final List<String> slides;
  final String localePrefix;
  final VoidCallback onDiagnose;
  final VoidCallback onResources;
  const _HeroSlideshow({
    required this.slides,
    required this.localePrefix,
    required this.onDiagnose,
    required this.onResources,
  });

  @override
  State<_HeroSlideshow> createState() => _HeroSlideshowState();
}

class _HeroSlideshowState extends State<_HeroSlideshow> {
  int _idx = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 6), (_) {
      if (!mounted) return;
      setState(() => _idx = (_idx + 1) % widget.slides.length);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final img = widget.slides[_idx];
    return Stack(
      fit: StackFit.expand,
      children: [
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 600),
          child: Image.asset(
            img,
            key: ValueKey(_idx),
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(color: const Color(0xFF1E3A8A)),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [Colors.transparent, Colors.black.withOpacity(0.55)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Spacer(),
              Text('Wherever you go,', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: Colors.white, height: 1.25, shadows: _textShadow)),
              Text('life is infinite', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: Color(0xFFFBBF24), fontStyle: FontStyle.italic, height: 1.25, shadows: _textShadow)),
              const SizedBox(height: 2),
              Text(widget.localePrefix, style: TextStyle(fontSize: 10.5, color: Colors.white.withOpacity(0.95), shadows: _textShadow)),
            ],
          ),
        ),
        Positioned(
          left: 0, right: 0, bottom: 4,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(widget.slides.length, (i) {
              final active = i == _idx;
              return Container(
                width: active ? 14 : 6,
                height: 4,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: active ? Colors.white : Colors.white.withOpacity(0.55),
                  borderRadius: BorderRadius.circular(2),
                ),
              );
            }),
          ),
        ),
      ],
    );
  }
}

const _textShadow = <Shadow>[
  Shadow(color: Color(0x88000000), blurRadius: 6, offset: Offset(0, 1)),
];
