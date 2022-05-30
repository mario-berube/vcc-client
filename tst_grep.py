import subprocess


def read_line(path):

    command = f'grep -b "Log Opened" {path} | tail -1'
    st_out, st_err = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).communicate()

    line = st_out.decode('utf-8')
    print(st_out.decode('utf-8'))
    pos = int(line.split(':')[0])
    print('POS', pos)
    with open(path, 'r') as file:
        file.seek(pos)
        line = file.readline()
        print(line)

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser( description='Station Listener' )
    parser.add_argument('path')

    args = parser.parse_args()

    read_line(args.path)


