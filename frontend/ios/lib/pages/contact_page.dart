// ContactPage — contact info (W32 web ContactView port).

import 'package:flutter/material.dart';

class ContactPage extends StatelessWidget {
  const ContactPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.of(context).maybePop()),
        title: const Text('联系我们', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text('我们在这里帮你', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
          const SizedBox(height: 4),
          const Text('工作日 9:00-18:00 (UTC+8) 小时内回复', style: TextStyle(fontSize: 13, color: Color(0xFF64748B))),
          const SizedBox(height: 24),
          _contactCard(
            icon: Icons.email_outlined,
            title: '邮箱',
            value: 'support@htex.app',
            subtitle: '所有问题 24 小时内回复',
            onTap: () {},
          ),
          _contactCard(
            icon: Icons.chat_outlined,
            title: '在线客服',
            value: 'App 内 "我的" → 客服',
            subtitle: '工作日实时回复',
            onTap: () {},
          ),
          _contactCard(
            icon: Icons.bug_report_outlined,
            title: 'Bug 反馈',
            value: '在 App 内 "我的" → 反馈',
            subtitle: '工程师直接收到',
            onTap: () {},
          ),
          _contactCard(
            icon: Icons.business_outlined,
            title: '商务合作',
            value: 'biz@htex.app',
            subtitle: 'Affiliate / 旅行社',
            onTap: () {},
          ),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(12)),
            child: const Row(children: [
              Icon(Icons.lightbulb_outline, size: 20, color: Color(0xFF3B6EF5)),
              SizedBox(width: 10),
              Expanded(child: Text('紧急情况请直接联系所在国的大使馆或领事馆。Htex 不能代替官方渠道。',
                  style: TextStyle(fontSize: 13, color: Color(0xFF0F172A)))),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _contactCard({required IconData icon, required String title, required String value, required String subtitle, required VoidCallback onTap}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: const BorderSide(color: Color(0xFFE2E8F0))),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(children: [
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(10)),
              alignment: Alignment.center,
              child: Icon(icon, color: const Color(0xFF3B6EF5), size: 22),
            ),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(fontSize: 14, color: Color(0xFF0F172A), fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text(subtitle, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
            ])),
          ]),
        ),
      ),
    );
  }
}