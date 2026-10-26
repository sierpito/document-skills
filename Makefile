test:
	python3 -m unittest discover -s tests -v

validate:
	python3 -I tools/validate_marketplace.py
