// main.dart — ReviewLens Flutter App (Linear SVC backend)
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:fl_chart/fl_chart.dart';

const String BASE_URL = 'http://10.0.2.2:8000'; // emulator
// const String BASE_URL = 'http://YOUR_LAPTOP_IP:8000'; // real phone

void main() => runApp(const ReviewLensApp());

class ReviewLensApp extends StatelessWidget {
  const ReviewLensApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ReviewLens',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _urlController = TextEditingController();
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _result;

  Future<void> _analyze() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;
    setState(() { _loading = true; _error = null; _result = null; });
    try {
      final res = await http.post(
        Uri.parse('$BASE_URL/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'product_url': url}),
      ).timeout(const Duration(seconds: 60));
      if (res.statusCode == 200) {
        setState(() { _result = jsonDecode(res.body); });
      } else {
        final body = jsonDecode(res.body);
        setState(() { _error = body['detail'] ?? 'Unknown error'; });
      }
    } catch (e) {
      setState(() { _error = 'Connection failed: $e'; });
    } finally {
      setState(() { _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('ReviewLens — Linear SVC'),
        backgroundColor: Colors.deepOrange,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextField(
            controller: _urlController,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              labelText: 'Daraz Product URL',
              hintText: 'https://www.daraz.pk/products/...',
              prefixIcon: Icon(Icons.link),
            ),
            maxLines: 2,
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: _loading ? null : _analyze,
            icon: const Icon(Icons.analytics),
            label: Text(_loading ? 'Analyzing...' : 'Analyze Reviews'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.all(16),
              backgroundColor: Colors.deepOrange,
              foregroundColor: Colors.white,
            ),
          ),
          const SizedBox(height: 20),
          if (_loading) const Center(child: Column(children: [
            CircularProgressIndicator(color: Colors.deepOrange),
            SizedBox(height: 12),
            Text('Linear SVC analyzing reviews (10-30 sec)...'),
          ])),
          if (_error != null) Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.red.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red),
            ),
            child: Row(children: [
              const Icon(Icons.error, color: Colors.red),
              const SizedBox(width: 8),
              Expanded(child: Text(_error!)),
            ]),
          ),
          if (_result != null) _buildResult(),
        ]),
      ),
    );
  }

  Widget _buildResult() {
    final summary = _result!['summary'];
    final pos = (summary['positive_percent'] as num).toDouble();
    final neg = (summary['negative_percent'] as num).toDouble();
    final neu = (summary['neutral_percent'] as num).toDouble();
    final total = _result!['total_reviews'];
    final praise = List<String>.from(_result!['common_praise']);
    final complaints = List<String>.from(_result!['common_complaints']);
    final samples = _result!['sample_reviews'] as List;

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
        Text('Analyzed $total reviews',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text('Powered by Linear SVC', style: TextStyle(fontSize: 12, color: Colors.grey[600])),
        const SizedBox(height: 16),
        SizedBox(height: 200, child: PieChart(PieChartData(sections: [
          PieChartSectionData(value: pos, color: Colors.green,
              title: '${pos.toStringAsFixed(0)}%',
              titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              radius: 80),
          PieChartSectionData(value: neg, color: Colors.red,
              title: '${neg.toStringAsFixed(0)}%',
              titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              radius: 80),
          PieChartSectionData(value: neu, color: Colors.grey,
              title: '${neu.toStringAsFixed(0)}%',
              titleStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              radius: 80),
        ]))),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          _legend(Colors.green, 'Positive (${summary["positive_count"]})'),
          _legend(Colors.red, 'Negative (${summary["negative_count"]})'),
          _legend(Colors.grey, 'Neutral (${summary["neutral_count"]})'),
        ]),
      ]))),

      if (praise.isNotEmpty) Card(color: Colors.green.shade50,
          child: Padding(padding: const EdgeInsets.all(16), child: Column(
              crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Common Praise',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8,
                children: praise.map((w) => Chip(
                    label: Text(w), backgroundColor: Colors.green.shade100)).toList()),
          ]))),

      if (complaints.isNotEmpty) Card(color: Colors.red.shade50,
          child: Padding(padding: const EdgeInsets.all(16), child: Column(
              crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Common Complaints',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8,
                children: complaints.map((w) => Chip(
                    label: Text(w), backgroundColor: Colors.red.shade100)).toList()),
          ]))),

      Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Sample Reviews',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...samples.map<Widget>((s) {
          Color c = s['sentiment'] == 'positive' ? Colors.green
              : s['sentiment'] == 'negative' ? Colors.red : Colors.grey;
          return ListTile(
            leading: Icon(Icons.circle, color: c, size: 14),
            title: Text(s['text'], maxLines: 3, overflow: TextOverflow.ellipsis),
            subtitle: Text('Rating: ${s["rating"]}/5 — ${s["sentiment"]} (${s["confidence"]}% confidence)'),
          );
        }),
      ]))),
    ]);
  }

  Widget _legend(Color c, String label) {
    return Row(children: [
      Container(width: 14, height: 14, color: c),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(fontSize: 11)),
    ]);
  }
}