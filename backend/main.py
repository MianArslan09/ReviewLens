# main.py — ReviewLens FastAPI Backend (Linear SVC Model + Hybrid Correction)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import re
import os
from collections import Counter

from scraper import scrape_daraz_reviews


# ==========================================================
# FastAPI Application Setup
# ==========================================================
app = FastAPI(title='ReviewLens API — Linear SVC')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)


# ==========================================================
# Load Trained Model (Executed Once at Startup)
# ==========================================================
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    'sentiment_model.pkl'
)

print(f'Loading Linear SVC model from {MODEL_PATH}')
model = joblib.load(MODEL_PATH)
print('Model loaded successfully')


# ==========================================================
# Text Cleaning Function
# IMPORTANT:
# Must match the preprocessing used during training.
# ==========================================================
def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ==========================================================
# Stopwords for Keyword Extraction
# ==========================================================
STOPWORDS = {
    'the', 'is', 'are', 'and', 'or', 'but', 'a', 'an', 'this',
    'that', 'i', 'it', 'to', 'for', 'of', 'in', 'on', 'with',
    'was', 'were', 'have', 'has', 'had', 'be', 'been', 'very',
    'so', 'too', 'product', 'item', 'my', 'me', 'you', 'your',
    'we', 'they', 'them', 'will', 'would', 'should', 'can'
}


# ==========================================================
# Roman Urdu Sentiment Keywords
# ==========================================================
POSITIVE_ROMAN_URDU = {
    'acha',
    'achi',
    'boht acha',
    'bht acha',
    'zabardast',
    'best',
    'recommended',
    'soft',
    'same as shown',
    'same to pic',
    'alhamdulillah',
    'excellent',
    'good quality',
    'value for money',
    'cooperative',
    'fast delivery',
    'worth buying',
    'original'
}

NEGATIVE_ROMAN_URDU = {
    'bekar',
    'kharab',
    'not good',
    'low quality',
    'wrong color',
    'different color',
    'fake',
    'damaged',
    'poor quality',
    'waste of money',
    'broken'
}


# ==========================================================
# Keyword Extraction
# ==========================================================
def extract_keywords(reviews: list, top_n: int = 5) -> list:
    all_words = []

    for review in reviews:
        words = clean_text(review).split()

        filtered_words = [
            word for word in words
            if len(word) > 3 and word not in STOPWORDS
        ]

        all_words.extend(filtered_words)

    counter = Counter(all_words)
    return [word for word, _ in counter.most_common(top_n)]


# ==========================================================
# Request Model
# ==========================================================
class AnalyzeRequest(BaseModel):
    product_url: str
    max_pages: int = 3


# ==========================================================
# Root Endpoint
# ==========================================================
@app.get('/')
def root():
    return {
        'status': 'ReviewLens API is running',
        'model': 'Linear SVC + CalibratedClassifierCV + Hybrid Rules',
        'dataset_trained': 'arhamrumi/amazon-product-reviews (568K reviews)',
        'endpoints': {
            'POST /analyze': 'Analyze reviews from a Daraz product URL'
        }
    }


# ==========================================================
# Analyze Endpoint
# ==========================================================
@app.post('/analyze')
def analyze(req: AnalyzeRequest):
    try:
        # ==================================================
        # 1. Extract Reviews
        # ==================================================
        print(f'Scraping: {req.product_url}')

        raw_reviews = scrape_daraz_reviews(
            req.product_url,
            req.max_pages
        )

        if not raw_reviews:
            raise HTTPException(
                status_code=404,
                detail='No reviews found. Try another product or check URL.'
            )

        # ==================================================
        # 2. Prepare Text
        # ==================================================
        review_texts = [review['text'] for review in raw_reviews]
        cleaned = [clean_text(text) for text in review_texts]

        # ==================================================
        # 3. Predict Sentiments
        # ==================================================
        predictions = list(model.predict(cleaned))
        probabilities = model.predict_proba(cleaned)

        # ==================================================
        # 4. Hybrid Rule-Based Correction
        # ==================================================
        for i in range(len(predictions)):
            text = review_texts[i].lower()
            rating = raw_reviews[i].get('rating', 0)
            confidence = float(max(probabilities[i]))
            pred = predictions[i]

            positive_hits = sum(
                1 for keyword in POSITIVE_ROMAN_URDU
                if keyword in text
            )

            negative_hits = sum(
                1 for keyword in NEGATIVE_ROMAN_URDU
                if keyword in text
            )

            # Strong positive indicators in high-rated reviews
            if pred == 'negative' and positive_hits >= 2 and rating >= 4:
                predictions[i] = 'positive'

            # Mixed positive and negative signals
            elif positive_hits >= 1 and negative_hits >= 1:
                predictions[i] = 'neutral'

            # High-rated reviews should rarely be strongly negative
            elif pred == 'negative' and rating >= 4 and confidence < 0.80:
                predictions[i] = 'neutral'

            # Five-star reviews with positive keywords
            elif rating == 5 and positive_hits >= 1 and confidence < 0.90:
                predictions[i] = 'positive'

        # ==================================================
        # 5. Calculate Summary Statistics
        # ==================================================
        total = len(predictions)

        pos = sum(1 for p in predictions if p == 'positive')
        neg = sum(1 for p in predictions if p == 'negative')
        neu = total - pos - neg

        # ==================================================
        # 6. Collect Positive and Negative Reviews
        # ==================================================
        positive_reviews = [
            review_texts[i]
            for i, prediction in enumerate(predictions)
            if prediction == 'positive'
        ]

        negative_reviews = [
            review_texts[i]
            for i, prediction in enumerate(predictions)
            if prediction == 'negative'
        ]

        # ==================================================
        # 7. Extract Keywords
        # ==================================================
        praise = (
            extract_keywords(positive_reviews)
            if positive_reviews else []
        )

        complaints = (
            extract_keywords(negative_reviews)
            if negative_reviews else []
        )

        # ==================================================
        # 8. Prepare Sample Reviews
        # ==================================================
        sample_reviews = []

        for i in range(min(10, total)):
            sample_reviews.append({
                'text': review_texts[i],
                'rating': raw_reviews[i]['rating'],
                'reviewer': raw_reviews[i].get('reviewer', 'Anonymous'),
                'sentiment': predictions[i],
                'confidence': round(
                    float(max(probabilities[i])) * 100,
                    1
                )
            })

        # ==================================================
        # 9. Return JSON Response
        # ==================================================
        return {
            'total_reviews': total,
            'summary': {
                'positive_percent': round(pos / total * 100, 1),
                'negative_percent': round(neg / total * 100, 1),
                'neutral_percent': round(neu / total * 100, 1),
                'positive_count': pos,
                'negative_count': neg,
                'neutral_count': neu,
            },
            'common_praise': praise,
            'common_complaints': complaints,
            'sample_reviews': sample_reviews
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f'ERROR: {e}')

        raise HTTPException(
            status_code=500,
            detail=f'Server error: {str(e)}'
        )

