// DiagnosePage — visa eligibility quick-check (W31/W32 feature).
//
// 3 steps:
//   1: country picker
//   2: profile form (marital / income / travel / visa history / employment / age / solo female)
//   3: result — score + level + factors + suggestions + CTA → ApplyPage

import 'package:flutter/material.dart';
import '../services/destinations_service.dart';
import '../services/diagnose_service.dart';
import 'apply_page.dart';

class DiagnosePage extends StatefulWidget {
  const DiagnosePage({super.key});

  @override
  State<DiagnosePage> createState() => _DiagnosePageState();
}

class _DiagnosePageState extends State<DiagnosePage> {
  int _step = 1;
  bool _loading = false;
  String? _error;

  String? _countryCode;
  List<Destination> _allCountries = const [];
  Map<String, List<Destination>> _grouped = const {};

  String _marital = 'single';
  String _income = '15k_30k';
  String _purpose = 'tourism';
  String _travelHistory = '1_3';
  String _visaHistory = 'none';
  String _employment = 'employed';
  int? _age;
  bool _isSoloFemale = false;

  DiagnoseResult? _result;

  final _destSvc = DestinationsService();
  final _diagSvc = DiagnoseService();

  @override
  void initState() {
    super.initState();
    _loadCountries();
  }

  Future<void> _loadCountries() async {
    setState(() => _loading = true);
    try {
      final list = await _destSvc.list(lang: 'zh-CN');
      // 产品口径: 美/英/澳 + 申根 DE·FR(与 web PRODUCT_COUNTRY_CODES 对齐)
      const product = {'US', 'GB', 'UK', 'AU', 'DE', 'FR'};
      final visible = list.where((d) => product.contains(d.countryCode)).toList();
      setState(() {
        _allCountries = visible;
        _grouped = _destSvc.groupByVisaType(visible);
      });
    } catch (_) {
      setState(() {
        _allCountries = DestinationsService.fallback();
        _grouped = _destSvc.groupByVisaType(_allCountries);
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _selectCountry(String cc) {
    setState(() {
      _countryCode = cc;
      _step = 2;
    });
  }

  bool get _canSubmit => _countryCode != null &&
      _marital.isNotEmpty && _income.isNotEmpty && _purpose.isNotEmpty &&
      _travelHistory.isNotEmpty && _visaHistory.isNotEmpty && _employment.isNotEmpty;

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await _diagSvc.submit(
        countryCode: _countryCode!,
        maritalStatus: _marital,
        incomeBucket: _income,
        travelPurpose: _purpose,
        travelHistory: _travelHistory,
        visaHistory: _visaHistory,
        employment: _employment,
        age: _age,
        isSoloFemale: _isSoloFemale,
      );
      setState(() {
        _result = r;
        _step = 3;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _restart() {
    setState(() {
      _step = 1;
      _result = null;
      _countryCode = null;
    });
  }

  void _goApply() {
    if (_countryCode == null) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ApplyPage(initialCountryCode: _countryCode)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Text(
          _stepTitle(_step),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A)),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: _step / 3,
            backgroundColor: const Color(0xFFE2E8F0),
            valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF10B981)),
          ),
        ),
      ),
      body: _buildStep(),
    );
  }

  String _stepTitle(int step) {
    switch (step) {
      case 1: return '通过率预评估';
      case 2: return '填写基本信息';
      case 3: return '评估结果';
      default: return '通过率预评估';
    }
  }

  Widget _buildStep() {
    if (_step == 1) return _buildCountryStep();
    if (_step == 2) return _buildFormStep();
    return _buildResultStep();
  }

  Widget _buildCountryStep() {
    if (_loading && _allCountries.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('你想去哪里？', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
        const SizedBox(height: 4),
        const Text('先了解通过率，再决定要不要正式申请。', style: TextStyle(fontSize: 14, color: Color(0xFF64748B))),
        const SizedBox(height: 24),
        if (_grouped['national']?.isNotEmpty ?? false) ...[
          _groupHeader('精选目的地', _grouped['national']!.length),
          const SizedBox(height: 12),
          _countryGrid(_grouped['national']!),
          const SizedBox(height: 24),
        ],
        if (_grouped['schengen']?.isNotEmpty ?? false) ...[
          _groupHeader('申根 26 国', _grouped['schengen']!.length),
          const SizedBox(height: 12),
          _countryGrid(_grouped['schengen']!),
        ],
      ],
    );
  }

  Widget _groupHeader(String title, int count) {
    return Row(children: [
      Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF475569))),
      const SizedBox(width: 8),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(999)),
        child: Text('$count', style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontWeight: FontWeight.w500)),
      ),
    ]);
  }

  Widget _countryGrid(List<Destination> items) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3, crossAxisSpacing: 10, mainAxisSpacing: 10, childAspectRatio: 1.05,
      ),
      itemCount: items.length,
      itemBuilder: (_, i) => _countryTile(items[i]),
    );
  }

  Widget _countryTile(Destination d) {
    final flag = _flagOf(d.countryCode);
    return InkWell(
      onTap: () => _selectCountry(d.countryCode),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFC),
          border: Border.all(color: const Color(0xFFE2E8F0)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(flag, style: const TextStyle(fontSize: 28)),
            const SizedBox(height: 6),
            Text(d.countryName,
                style: const TextStyle(fontSize: 12, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
                textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }

  String _flagOf(String cc) {
    const flags = {
      'US': '🇺🇸', 'JP': '🇯🇵', 'KR': '🇰🇷', 'SG': '🇸🇬', 'GB': '🇬🇧', 'FR': '🇫🇷',
      'ID': '🇮🇩', 'VN': '🇻🇳', 'TH': '🇹🇭', 'DE': '🇩🇪', 'AU': '🇦🇺', 'CA': '🇨🇦',
      'NZ': '🇳🇿', 'SCHENGEN': '🇪🇺',
    };
    return flags[cc] ?? '🌐';
  }

  Widget _buildFormStep() {
    final cc = _allCountries.firstWhere((d) => d.countryCode == _countryCode, orElse: () => DestinationsService.fallback().first);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(children: [
          Text(_flagOf(cc.countryCode), style: const TextStyle(fontSize: 22)),
          const SizedBox(width: 6),
          Text(cc.countryName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        ]),
        const SizedBox(height: 16),
        _pillGroup('婚姻状况', 'marital', _marital, {
          'single': '未婚', 'married': '已婚', 'divorced': '离异', 'widowed': '丧偶',
        }, (v) => setState(() => _marital = v)),
        _pillGroup('月收入 (人民币)', 'income', _income, {
          'below_5k': '<5k', '5k_15k': '5k-15k', '15k_30k': '15k-30k',
          '30k_100k': '30k-100k', 'above_100k': '>100k',
        }, (v) => setState(() => _income = v)),
        _pillGroup('出行目的', 'purpose', _purpose, {
          'business': '商务', 'tourism': '旅游', 'family': '探亲', 'study': '留学', 'other': '其他',
        }, (v) => setState(() => _purpose = v)),
        _pillGroup('过去 5 年出行记录', 'travel', _travelHistory, {
          'none': '无', '1_3': '1-3 次', '4_10': '4-10 次', 'above_10': '10+ 次',
        }, (v) => setState(() => _travelHistory = v)),
        _pillGroup('签证历史', 'visa', _visaHistory, {
          'none': '无', '1_2': '1-2 次', 'above_2': '2+ 次',
        }, (v) => setState(() => _visaHistory = v)),
        _pillGroup('在职状态', 'employment', _employment, {
          'employed': '在职', 'freelancer': '自由职业', 'student': '学生', 'retired': '退休', 'unemployed': '待业',
        }, (v) => setState(() => _employment = v)),
        const SizedBox(height: 16),
        const Text('年龄 (选填)', style: TextStyle(fontSize: 13, color: Color(0xFF475569), fontWeight: FontWeight.w500)),
        const SizedBox(height: 8),
        TextField(
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(hintText: '如：30', border: OutlineInputBorder()),
          onChanged: (v) => _age = int.tryParse(v),
        ),
        const SizedBox(height: 12),
        SwitchListTile(
          value: _isSoloFemale,
          onChanged: (v) => setState(() => _isSoloFemale = v),
          title: const Text('是否单身女性独自旅行', style: TextStyle(fontSize: 13)),
          contentPadding: EdgeInsets.zero,
        ),
        const SizedBox(height: 24),
        if (_error != null) Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(_error!, style: const TextStyle(color: Colors.red)),
        ),
        ElevatedButton(
          onPressed: _loading || !_canSubmit ? null : _submit,
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF10B981),
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
          child: Text(_loading ? '评估中…' : '查看评估结果'),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: () => setState(() => _step = 1), child: const Text('← 重新选国家')),
      ],
    );
  }

  Widget _pillGroup(String label, String testId, String value, Map<String, String> options, void Function(String) onTap) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: Color(0xFF475569), fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: options.entries.map((e) {
              final selected = value == e.key;
              return InkWell(
                onTap: () => onTap(e.key),
                borderRadius: BorderRadius.circular(999),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: selected ? const Color(0xFF10B981) : Colors.white,
                    border: Border.all(color: selected ? const Color(0xFF10B981) : const Color(0xFFE2E8F0)),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(e.value,
                      style: TextStyle(fontSize: 13, color: selected ? Colors.white : const Color(0xFF475569))),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildResultStep() {
    if (_result == null) return const Center(child: CircularProgressIndicator());
    final r = _result!;
    final cc = _allCountries.firstWhere((d) => d.countryCode == _countryCode, orElse: () => DestinationsService.fallback().first);
    Color levelColor;
    String levelText;
    switch (r.level) {
      case 'high': levelColor = const Color(0xFF10B981); levelText = '通过率高'; break;
      case 'low': levelColor = const Color(0xFFEF4444); levelText = '通过率低'; break;
      default: levelColor = const Color(0xFFF59E0B); levelText = '中等';
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [levelColor.withOpacity(0.1), levelColor.withOpacity(0.02)]),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: levelColor.withOpacity(0.3)),
          ),
          child: Column(
            children: [
              Text('${_flagOf(cc.countryCode)} ${cc.countryName}', style: const TextStyle(fontSize: 14, color: Color(0xFF64748B))),
              const SizedBox(height: 8),
              Text('${r.score}', style: TextStyle(fontSize: 56, fontWeight: FontWeight.w800, color: levelColor)),
              Text('分 · $levelText', style: TextStyle(fontSize: 16, color: levelColor, fontWeight: FontWeight.w600)),
              if (r.policySummary != null) ...[
                const SizedBox(height: 12),
                Text(r.policySummary!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
              ],
            ],
          ),
        ),
        const SizedBox(height: 24),
        const Text('影响因素', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        const SizedBox(height: 12),
        ...r.factors.map((f) => _factorTile(f)),
        const SizedBox(height: 24),
        const Text('改进建议', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        const SizedBox(height: 12),
        ...r.suggestions.map((s) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('· ', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.w700)),
            Expanded(child: Text(s, style: const TextStyle(fontSize: 14, color: Color(0xFF475569)))),
          ]),
        )),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _goApply,
          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(vertical: 14)),
          child: const Text('继续申请这个国家 →'),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: _restart, child: const Text('重新评估')),
      ],
    );
  }

  Widget _factorTile(DiagnoseFactor f) {
    final isPos = f.impact >= 0;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE2E8F0)), borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        Container(
          width: 48,
          padding: const EdgeInsets.symmetric(vertical: 4),
          decoration: BoxDecoration(
            color: isPos ? const Color(0xFF10B981) : const Color(0xFFEF4444),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text('${isPos ? '+' : ''}${f.impact}', textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13)),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(f.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
            Text(f.detail, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
          ],
        )),
      ]),
    );
  }
}