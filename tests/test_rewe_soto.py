"""Unit tests for REWE SOTO product availability checking."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.scrapers.rewe import REWEScraper
from src.scrapers.base import Store


@pytest.fixture
def rewe_scraper():
    """Create a REWE scraper instance."""
    return REWEScraper(states=['Berlin'])


@pytest.fixture
def sample_store():
    """Create a sample REWE store for testing."""
    return Store(
        chain_id='rewe',
        store_id='762432',
        name='REWE Schmidt',
        street='Schönhauser Allee 80',
        postal_code='10439',
        city='Berlin',
        country_code='DE',
        latitude=52.5437,
        longitude=13.4125
    )


class TestSelectMarket:
    """Test market selection functionality."""

    @patch('src.scrapers.rewe.requests.post')
    def test_select_market_success(self, mock_post, rewe_scraper):
        """Test successful market selection."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        result = rewe_scraper._select_market('762432', {})

        assert result is True
        assert mock_post.called
        call_args = mock_post.call_args

        # Verify correct endpoint
        assert 'wksmarketselection' in call_args[0][0]

        # Verify payload structure
        payload = call_args[1]['json']
        assert payload['wwIdent'] == '762432'
        assert payload['selectedService'] == 'STATIONARY'

    @patch('src.scrapers.rewe.requests.post')
    def test_select_market_failure(self, mock_post, rewe_scraper):
        """Test market selection with failed response."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = rewe_scraper._select_market('762432', {})

        assert result is False

    @patch('src.scrapers.rewe.requests.post')
    def test_select_market_exception(self, mock_post, rewe_scraper):
        """Test market selection with network exception."""
        # Mock exception
        mock_post.side_effect = Exception("Network error")

        result = rewe_scraper._select_market('762432', {})

        assert result is False


class TestCheckSOTOAvailability:
    """Test SOTO product availability checking."""

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_with_products(self, mock_get, rewe_scraper):
        """Test SOTO check when products are available."""
        # Mock response with SOTO products
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'totalHits': 5}
        mock_get.return_value = mock_response

        count = rewe_scraper._check_soto_availability({})

        assert count == 5
        assert mock_get.called

        # Verify correct endpoint and query
        call_args = mock_get.call_args
        assert 'stationary-product-search/products/count' in call_args[0][0]
        assert call_args[1]['params']['query'] == '"SOTO"'

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_without_products(self, mock_get, rewe_scraper):
        """Test SOTO check when no products found."""
        # Mock response with no SOTO products
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'totalHits': 0}
        mock_get.return_value = mock_response

        count = rewe_scraper._check_soto_availability({})

        assert count == 0

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_api_error(self, mock_get, rewe_scraper):
        """Test SOTO check with API error raises exception."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # Should raise exception on non-200 status
        with pytest.raises(Exception, match="API returned status 500"):
            rewe_scraper._check_soto_availability({})

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_exception(self, mock_get, rewe_scraper):
        """Test SOTO check with network exception."""
        # Mock exception
        mock_get.side_effect = Exception("Network error")

        # Should propagate the exception
        with pytest.raises(Exception, match="Network error"):
            rewe_scraper._check_soto_availability({})

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_uses_exact_search(self, mock_get, rewe_scraper):
        """Test that SOTO check uses exact search with quotes."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'totalHits': 3}
        mock_get.return_value = mock_response

        rewe_scraper._check_soto_availability({})

        # Verify exact search query with quotes
        call_args = mock_get.call_args
        query = call_args[1]['params']['query']
        assert query == '"SOTO"'
        assert query.startswith('"')
        assert query.endswith('"')


class TestEnrichWithSOTO:
    """Test enriching stores with SOTO availability."""

    @patch.object(REWEScraper, '_select_market')
    @patch.object(REWEScraper, '_check_soto_availability')
    def test_enrich_store_with_soto(self, mock_check, mock_select,
                                    rewe_scraper, sample_store):
        """Test enriching a store that has SOTO products."""
        # Mock successful selection and SOTO check
        mock_select.return_value = True
        mock_check.return_value = 5

        enriched_store = rewe_scraper._enrich_with_soto(sample_store, {})

        assert enriched_store.has_soto_products is True
        assert mock_select.called
        assert mock_check.called

    @patch.object(REWEScraper, '_select_market')
    @patch.object(REWEScraper, '_check_soto_availability')
    def test_enrich_store_without_soto(self, mock_check, mock_select,
                                       rewe_scraper, sample_store):
        """Test enriching a store that has no SOTO products."""
        # Mock successful selection but no SOTO
        mock_select.return_value = True
        mock_check.return_value = 0

        enriched_store = rewe_scraper._enrich_with_soto(sample_store, {})

        assert enriched_store.has_soto_products is False

    @patch.object(REWEScraper, '_select_market')
    def test_enrich_store_selection_failed(self, mock_select,
                                          rewe_scraper, sample_store):
        """Test enriching when market selection fails."""
        # Mock failed selection
        mock_select.return_value = False

        enriched_store = rewe_scraper._enrich_with_soto(sample_store, {})

        # Should mark as unknown when selection fails
        assert enriched_store.has_soto_products is None

    @patch.object(REWEScraper, '_select_market')
    @patch.object(REWEScraper, '_check_soto_availability')
    def test_enrich_with_soto_retry_logic(self, mock_check, mock_select,
                                         rewe_scraper, sample_store):
        """Test retry logic when enriching fails."""
        # Mock selection success, check failure then success
        mock_select.return_value = True
        mock_check.side_effect = [Exception("Network error"), 3]

        enriched_store = rewe_scraper._enrich_with_soto_retry(sample_store, {})

        # Should succeed on retry
        assert enriched_store.has_soto_products is True
        assert mock_check.call_count == 2  # First fail, then succeed

    @patch.object(REWEScraper, '_select_market')
    @patch.object(REWEScraper, '_check_soto_availability')
    def test_enrich_with_soto_max_retries(self, mock_check, mock_select,
                                         rewe_scraper, sample_store):
        """Test that enrichment gives up after max retries."""
        # Mock continuous failures
        mock_select.return_value = True
        mock_check.side_effect = Exception("Network error")

        enriched_store = rewe_scraper._enrich_with_soto_retry(
            sample_store, {}, max_retries=2
        )

        # Should mark as unknown after max retries
        assert enriched_store.has_soto_products is None
        assert mock_check.call_count == 2


class TestSOTOHeadersAndImpersonation:
    """Test that SOTO checks use correct headers and browser impersonation."""

    @patch('src.scrapers.rewe.requests.post')
    def test_select_market_uses_impersonation(self, mock_post, rewe_scraper):
        """Test that market selection uses chrome impersonation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        rewe_scraper._select_market('762432', {'User-Agent': 'test'})

        call_args = mock_post.call_args
        assert call_args[1]['impersonate'] == 'chrome120'

    @patch('src.scrapers.rewe.requests.get')
    def test_check_soto_uses_impersonation(self, mock_get, rewe_scraper):
        """Test that SOTO check uses chrome impersonation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'totalHits': 0}
        mock_get.return_value = mock_response

        rewe_scraper._check_soto_availability({'User-Agent': 'test'})

        call_args = mock_get.call_args
        assert call_args[1]['impersonate'] == 'chrome120'

    @patch('src.scrapers.rewe.requests.post')
    def test_select_market_passes_headers(self, mock_post, rewe_scraper):
        """Test that market selection passes headers."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        headers = {'User-Agent': 'test-agent', 'Accept': 'application/json'}
        rewe_scraper._select_market('762432', headers)

        call_args = mock_post.call_args
        assert call_args[1]['headers'] == headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
