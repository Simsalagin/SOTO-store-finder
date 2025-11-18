"""Integration tests for REWE scraper with SOTO availability checking."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.scrapers.rewe import REWEScraper


@pytest.fixture
def mock_market_search_response():
    """Create a mock response for marketSearch API."""
    return {
        'markets': [
            {
                'wwIdent': '762432',
                'marketName': 'REWE',
                'companyName': 'Schmidt oHG',
                'street': 'Schönhauser Allee 80',
                'zipCode': '10439',
                'city': 'Berlin',
            },
            {
                'wwIdent': '762433',
                'marketName': 'REWE',
                'companyName': 'Test GmbH',
                'street': 'Test Str. 1',
                'zipCode': '10115',
                'city': 'Berlin',
            },
        ],
        'totalHits': 2
    }


@pytest.fixture
def mock_market_details_response():
    """Create a mock response for market details API."""
    return {
        'markets': [
            {
                'wwIdent': '762432',
                'location': {
                    'latitude': 52.5437,
                    'longitude': 13.4125
                },
                'openingInfo': []
            },
            {
                'wwIdent': '762433',
                'location': {
                    'latitude': 52.5200,
                    'longitude': 13.4050
                },
                'openingInfo': []
            },
        ]
    }


class TestREWEScraperIntegration:
    """Integration tests for REWE scraper with SOTO checking."""

    @patch('src.scrapers.rewe.requests.post')
    @patch('src.scrapers.rewe.requests.get')
    def test_scrape_with_soto_checking_enabled(
        self, mock_get, mock_post, mock_market_search_response, mock_market_details_response
    ):
        """Test full scrape flow with SOTO checking enabled."""
        # Setup mock responses
        # 1. Market search returns 2 stores
        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = mock_market_search_response

        # 2. Market details for coordinates
        mock_details_response = Mock()
        mock_details_response.status_code = 200
        mock_details_response.json.return_value = mock_market_details_response

        # 3. Market selection succeeds
        mock_selection_response = Mock()
        mock_selection_response.status_code = 201

        # 4. SOTO count API - first store has SOTO, second doesn't
        mock_soto_response_1 = Mock()
        mock_soto_response_1.status_code = 200
        mock_soto_response_1.json.return_value = {'totalHits': 5}

        mock_soto_response_2 = Mock()
        mock_soto_response_2.status_code = 200
        mock_soto_response_2.json.return_value = {'totalHits': 0}

        # Configure mock_get to return appropriate response based on URL
        def get_side_effect(url, **kwargs):
            if 'wksmarketsearch' in url:
                return mock_details_response
            elif 'stationary-product-search/products/count' in url:
                # Return different SOTO counts alternately
                if not hasattr(get_side_effect, 'soto_call_count'):
                    get_side_effect.soto_call_count = 0
                get_side_effect.soto_call_count += 1
                return mock_soto_response_1 if get_side_effect.soto_call_count == 1 else mock_soto_response_2
            return Mock(status_code=404)

        mock_get.side_effect = get_side_effect

        # Configure mock_post for market search and selection
        def post_side_effect(url, **kwargs):
            if 'marketSearch' in url:
                # Return empty markets after first page to stop pagination
                if not hasattr(post_side_effect, 'call_count'):
                    post_side_effect.call_count = 0
                post_side_effect.call_count += 1
                if post_side_effect.call_count == 1:
                    return mock_search_response
                else:
                    empty_response = Mock()
                    empty_response.status_code = 200
                    empty_response.json.return_value = {'markets': [], 'totalHits': 0}
                    return empty_response
            elif 'wksmarketselection' in url:
                return mock_selection_response
            return Mock(status_code=404)

        mock_post.side_effect = post_side_effect

        # Create scraper with check_soto_availability=True
        scraper = REWEScraper(states=['Berlin'])
        scraper.check_soto_availability = True

        # Run scraper
        stores = scraper.scrape()

        # Verify we got 2 stores
        assert len(stores) == 2

        # Verify SOTO flags are set correctly
        # First store has SOTO, second doesn't
        assert stores[0].has_soto_products is True
        assert stores[1].has_soto_products is False

    @patch('src.scrapers.rewe.requests.post')
    @patch('src.scrapers.rewe.requests.get')
    def test_scrape_integration_with_soto_flags(
        self, mock_get, mock_post, mock_market_search_response, mock_market_details_response
    ):
        """Test that scraper sets SOTO flags when enabled (this will pass after integration)."""
        # Setup similar to above but expecting SOTO flags to be set
        # This test documents the expected behavior after integration

        # Setup mock responses
        mock_search_response = Mock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = mock_market_search_response

        mock_details_response = Mock()
        mock_details_response.status_code = 200
        mock_details_response.json.return_value = mock_market_details_response

        mock_selection_response = Mock()
        mock_selection_response.status_code = 201

        # First store has SOTO, second doesn't
        soto_responses = [
            Mock(status_code=200, json=lambda: {'totalHits': 5}),  # Has SOTO
            Mock(status_code=200, json=lambda: {'totalHits': 0}),  # No SOTO
        ]
        soto_call_count = [0]

        def get_side_effect(url, **kwargs):
            if 'wksmarketsearch' in url:
                return mock_details_response
            elif 'stationary-product-search/products/count' in url:
                response = soto_responses[min(soto_call_count[0], len(soto_responses) - 1)]
                soto_call_count[0] += 1
                return response
            return Mock(status_code=404)

        mock_get.side_effect = get_side_effect

        call_count = [0]
        def post_side_effect(url, **kwargs):
            if 'marketSearch' in url:
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_search_response
                else:
                    empty_response = Mock()
                    empty_response.status_code = 200
                    empty_response.json.return_value = {'markets': [], 'totalHits': 0}
                    return empty_response
            elif 'wksmarketselection' in url:
                return mock_selection_response
            return Mock(status_code=404)

        mock_post.side_effect = post_side_effect

        # Create scraper with SOTO checking enabled
        scraper = REWEScraper(states=['Berlin'])
        scraper.check_soto_availability = True

        # Run scraper
        stores = scraper.scrape()

        # Verify stores and SOTO flags
        assert len(stores) == 2
        assert stores[0].has_soto_products is True  # First store has SOTO
        assert stores[1].has_soto_products is False  # Second store doesn't


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
