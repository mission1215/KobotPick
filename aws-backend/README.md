# kobotpick-aws-backend

KobotPick AWS Lambda backend.

- `lambda_function.py` : Lambda entrypoint + 간단한 라우팅(`/health`, `/headlines`)
- 나중에 `/recommendations`, DynamoDB 연동 등을 여기서 확장

## Lambda 패키징 팁
- `deploy.zip`은 **리눅스용(amazonlinux/manylinux)** 빌드된 패키지를 사용해야 합니다. macOS에서 `pip install -t .`으로 생성한 `.so` 파일(`_cffi_backend.cpython-311-darwin.so` 등)은 Lambda에서 `invalid ELF header` 오류를 일으킵니다.
- 로컬이 macOS라면 Docker에서 빌드하세요:
  ```
  docker run --rm -v "$PWD":/var/task -w /var/task public.ecr.aws/lambda/python:3.12 \
    /bin/bash -lc "pip install --upgrade pip && pip install -r requirements.txt -t . --only-binary=:all: --platform manylinux2014_x86_64 --implementation cp --python-version 312"
  zip -r deploy.zip lambda_function.py core models *.py requirements.txt *.dist-info *.data
  ```
- `yfinance`가 `pandas`, `numpy`, `lxml`, `html5lib`, `beautifulsoup4` 등에 의존하므로 누락하면 `ModuleNotFoundError: pandas`류가 발생합니다. `requirements.txt`를 기준으로 의존성을 모두 포함해 패키징하세요.
