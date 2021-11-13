.PHONY: clean


minica:
	go mod init minica-api-lib
	go get -d github.com/bjornsnoen/minica@v1.1.0
	go build --buildmode=c-shared github.com/bjornsnoen/minica

clean:
	rm -rf go.mod minica minica.h go.sum