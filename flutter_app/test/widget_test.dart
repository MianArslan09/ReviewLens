import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_app/main.dart';

void main() {
  testWidgets('ReviewLens app loads smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ReviewLensApp());

    // Verify that the AppBar title is present on the screen.
    expect(find.text('ReviewLens — Linear SVC'), findsOneWidget);
  });
}