# main.py — ReviewLens FastAPI Backend (Linear SVC Model)

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
# This must be identical to the preprocessing used during training.
# ==========================================================
def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r'http\S+', '', text)       # Remove URLs
    text = re.sub(r'<.*?>', '', text)         # Remove HTML tags
    text = re.sub(r'[^a-z\s]', '', text)      # Keep only letters and spaces
    text = re.sub(r'\s+', ' ', text).strip()  # Remove extra spaces
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
# Keyword Extraction
# ==========================================================
def extract_keywords(reviews: list, top_n: int = 5) -> list:
    """
    Extract most common meaningful words from review texts.
    """
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
    product_url: str          # Daraz product URL
    max_pages: int = 3        # Number of review pages to scrape


# ==========================================================
# Root Endpoint
# ==========================================================
@app.get('/')
def root():
    return {
        'status': 'ReviewLens API is running',
        'model': 'Linear SVC + CalibratedClassifierCV',
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
        predictions = model.predict(cleaned)

        # Since model uses CalibratedClassifierCV,
        # predict_proba() is available
        probabilities = model.predict_proba(cleaned)

        # ==================================================
        # 4. Calculate Summary Statistics
        # ==================================================
        total = len(predictions)

        pos = sum(1 for p in predictions if p == 'positive')
        neg = sum(1 for p in predictions if p == 'negative')
        neu = total - pos - neg

        # ==================================================
        # 5. Collect Positive and Negative Reviews
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
        # 6. Extract Keywords
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
        # 7. Prepare Sample Reviews (First 10)
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
        # 8. Return JSON Response
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

    # Invalid URL format
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # Re-raise FastAPI exceptions unchanged
    except HTTPException:
        raise

    # Unexpected server errors
    except Exception as e:
        print(f'ERROR: {e}')

        raise HTTPException(
            status_code=500,
            detail=f'Server error: {str(e)}'
        )