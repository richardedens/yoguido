#!/bin/bash
cp .pypirc ~/.pypirc
py -m twine upload dist/* --verbose