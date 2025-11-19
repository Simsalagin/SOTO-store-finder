"""
Tests for REWE batch generator with SOTO checking.
Following TDD: These tests are written BEFORE implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List


class TestREWEBatchGenerator:
    """Test suite for REWE incremental batch scraping with SOTO."""

    @pytest.fixture
    def mock_rewe_response_page_0(self):
        """Mock REWE API response for page 0."""
        return {
            'markets': [
                {
                    'wwIdent': 'rewe_1',
                    'marketName': 'REWE',
                    'companyName': 'REWE Markt GmbH',
                    'street': '1 Test St',
                    'zipCode': '10115',
                    'city': 'Berlin'
                },
                {
                    'wwIdent': 'rewe_2',
                    'marketName': 'REWE',
                    'companyName': 'REWE Markt GmbH',
                    'street': '2 Test St',
                    'zipCode': '10115',
                    'city': 'Berlin'
                }
            ],
            'totalHits': 200
        }

    @pytest.fixture
    def mock_rewe_response_empty(self):
        """Mock empty REWE API response (last page)."""
        return {
            'markets': [],
            'totalHits': 200
        }

    @pytest.fixture
    def mock_coordinates_response(self):
        """Mock coordinates enrichment response."""
        return {
            'markets': [
                {
                    'wwIdent': 'rewe_1',
                    'location': {
                        'latitude': 52.52,
                        'longitude': 13.40
                    }
                }
            ]
        }

    def test_generate_batches_yields_one_page_at_a_time(self, mock_rewe_response_page_0, mock_rewe_response_empty):
        """Test that _generate_batches yields one page per batch."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"])

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            # Mock API responses: page 0 has 2 stores, page 1 is empty
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            # Mock coordinates response
            mock_get.return_value = Mock(status_code=200, json=lambda: {'markets': []})

            # Generate batches
            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # Should yield 1 batch (page 0 with 2 stores, page 1 empty stops iteration)
            assert len(batches) == 1
            assert len(batches[0]) == 2

    def test_generate_batches_includes_soto_check_when_enabled(
        self, mock_rewe_response_page_0, mock_rewe_response_empty
    ):
        """Test that SOTO checking happens during batch generation."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"], check_soto_availability=True)

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            # Mock market search response
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            # Mock coordinates and SOTO responses
            mock_get.side_effect = [
                # Coordinates for store 1
                Mock(status_code=200, json=lambda: {'markets': []}),
                # Market selection for store 1
                Mock(status_code=201),
                # SOTO count for store 1
                Mock(status_code=200, json=lambda: {'totalHits': 5}),
                # Coordinates for store 2
                Mock(status_code=200, json=lambda: {'markets': []}),
                # Market selection for store 2
                Mock(status_code=201),
                # SOTO count for store 2
                Mock(status_code=200, json=lambda: {'totalHits': 0}),
            ]

            # Generate batches
            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # Verify SOTO fields are set
            assert len(batches) == 1
            batch = batches[0]
            assert len(batch) == 2

            # Store 1 should have SOTO
            assert batch[0].has_soto_products is True
            # Store 2 should not have SOTO
            assert batch[1].has_soto_products is False

    def test_generate_batches_skips_soto_when_disabled(
        self, mock_rewe_response_page_0, mock_rewe_response_empty
    ):
        """Test that SOTO checking is skipped when check_soto_availability=False."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"], check_soto_availability=False)

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            mock_get.return_value = Mock(status_code=200, json=lambda: {'markets': []})

            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # SOTO check API should not be called (only coordinates)
            # Coordinates are called via wksmarketsearch, SOTO via product count
            product_count_calls = [
                call for call in mock_get.call_args_list
                if 'products/count' in str(call)
            ]
            assert len(product_count_calls) == 0

    def test_generate_batches_respects_limit(
        self, mock_rewe_response_page_0, mock_rewe_response_empty
    ):
        """Test that limit parameter stops generation early."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin", "Hamburg"])

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            # Mock: Berlin page 0 has 2 stores, Hamburg should not be reached
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            mock_get.return_value = Mock(status_code=200, json=lambda: {'markets': []})

            # Generate with limit of 1 store
            batches = list(scraper._generate_batches(batch_size=100, limit=1))

            # Should stop after first batch (has 2 stores, but limit is 1)
            assert len(batches) == 1
            # Batch should be trimmed to limit
            assert len(batches[0]) <= 1

    def test_generate_batches_handles_multiple_states(self):
        """Test that generator processes multiple states."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin", "Hamburg"])

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            # Mock responses for Berlin and Hamburg
            mock_post.side_effect = [
                # Berlin page 0
                Mock(status_code=200, json=lambda: {
                    'markets': [
                        {'wwIdent': 'berlin_1', 'marketName': 'REWE', 'companyName': 'REWE',
                         'street': 'St', 'zipCode': '10115', 'city': 'Berlin'}
                    ],
                    'totalHits': 1
                }),
                # Berlin page 1 (empty)
                Mock(status_code=200, json=lambda: {'markets': [], 'totalHits': 1}),
                # Hamburg page 0
                Mock(status_code=200, json=lambda: {
                    'markets': [
                        {'wwIdent': 'hamburg_1', 'marketName': 'REWE', 'companyName': 'REWE',
                         'street': 'St', 'zipCode': '20095', 'city': 'Hamburg'}
                    ],
                    'totalHits': 1
                }),
                # Hamburg page 1 (empty)
                Mock(status_code=200, json=lambda: {'markets': [], 'totalHits': 1}),
            ]

            mock_get.return_value = Mock(status_code=200, json=lambda: {'markets': []})

            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # Should have 2 batches (1 per state)
            assert len(batches) == 2
            assert batches[0][0].city == 'Berlin'
            assert batches[1][0].city == 'Hamburg'

    def test_generate_batches_enriches_coordinates(
        self, mock_rewe_response_page_0, mock_rewe_response_empty
    ):
        """Test that coordinates are enriched during batch generation."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"])

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            # Mock coordinates enrichment
            mock_get.return_value = Mock(status_code=200, json=lambda: {
                'markets': [
                    {
                        'wwIdent': 'rewe_1',
                        'location': {'latitude': 52.52, 'longitude': 13.40}
                    },
                    {
                        'wwIdent': 'rewe_2',
                        'location': {'latitude': 52.53, 'longitude': 13.41}
                    }
                ]
            })

            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # Verify coordinates are set
            assert batches[0][0].latitude == 52.52
            assert batches[0][0].longitude == 13.40
            assert batches[0][1].latitude == 52.53
            assert batches[0][1].longitude == 13.41

    def test_generate_batches_is_generator(self):
        """Test that _generate_batches returns a generator."""
        from src.scrapers.rewe import REWEScraper
        from typing import Generator

        scraper = REWEScraper(states=["Berlin"])

        result = scraper._generate_batches(batch_size=100, limit=None)

        # Should be a generator
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')

    def test_generate_batches_handles_api_errors_gracefully(self):
        """Test that generator handles API errors without crashing."""
        from src.scrapers.rewe import REWEScraper

        scraper = REWEScraper(states=["Berlin"])

        with patch('src.scrapers.rewe.requests.post') as mock_post:
            # Mock API error
            mock_post.return_value = Mock(status_code=500)

            batches = list(scraper._generate_batches(batch_size=100, limit=None))

            # Should return empty list (no crash)
            assert len(batches) == 0

    def test_batch_size_parameter_is_honored(
        self, mock_rewe_response_page_0, mock_rewe_response_empty
    ):
        """Test that batch_size parameter determines batch boundary."""
        from src.scrapers.rewe import REWEScraper

        # Note: For REWE, batch_size is somewhat semantic since we yield
        # one API page at a time (~100 stores), but we should still honor it
        # This test verifies the parameter is accepted
        scraper = REWEScraper(states=["Berlin"])

        with patch('src.scrapers.rewe.requests.post') as mock_post, \
             patch('src.scrapers.rewe.requests.get') as mock_get:

            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: mock_rewe_response_page_0),
                Mock(status_code=200, json=lambda: mock_rewe_response_empty)
            ]

            mock_get.return_value = Mock(status_code=200, json=lambda: {'markets': []})

            # Should accept batch_size parameter (even if REWE yields by page)
            batches = list(scraper._generate_batches(batch_size=50, limit=None))

            assert len(batches) >= 1  # At least one batch returned
