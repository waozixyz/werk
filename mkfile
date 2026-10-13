</$objtype/mkfile

# Generate with `make plan9-c` on the host, then build natively with `mk`.
CLI_FILES=`{ls build/plan9/cli/*.c}
CLI_HEADERS=`{ls build/plan9/cli/*.h}
CLI_OBJECTS=${CLI_FILES:%.c=%.$O}
CFLAGS=-FTVw

all:V: pass

pass: $CLI_OBJECTS
	$LD -o $target $prereq

$CLI_OBJECTS: $CLI_HEADERS

%.$O: %.c
	$CC $CFLAGS -o $target $stem.c

install:V: pass
	cp pass /$objtype/bin/pass
