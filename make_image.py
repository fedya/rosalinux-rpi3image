#!/usr/bin/env python
import os
import re
import sys
import subprocess
import requests

rootfs_dir = '/tmp/rpi3_dir/'
boot_dir = '/tmp/rpi3_dir/boot'

def prepare_rpi_disk():
    disk_image = 'disk_image.img'
    # dd if=/dev/zero of=rpi3_disk.img bs=1M count=1024
    print('creating {}'.format(disk_image))
    make_disk = subprocess.check_output(['/usr/bin/sudo', 'dd', 'if=/dev/zero', 'of=disk_image.img', 'bs=1M', 'count=1256'])
    command = ['sudo', '/sbin/fdisk', disk_image]
    p = subprocess.Popen(command, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    print("Partitioning the disk '{}'".format(disk_image))
    # it's just echo to fdisk
    output, err = p.communicate(b"o\nn\np\n1\n\n+200M\nt\nb\na\nn\np\n2\n\n\n\nw")
    # sudo losetup -f -P 2019-07-10-raspbian-buster-lite.img
    print("Mounting '{}' as /dev/loop device".format(disk_image))
    # sudo losetup -f -P disk_image.img --show
    losetup_connect = subprocess.check_output(['/usr/bin/sudo', 'losetup', '-f', '-P', 'disk_image.img', '--show'])
    lodevice = losetup_connect.decode('utf-8').strip()
    print('loopback device connected {}'.format(lodevice))
    print('making fs for loopback partiotions')
    mkfs_boot = subprocess.check_output(['sudo', '/sbin/mkfs.fat', '-n', 'BOOT','-F', '32', lodevice.strip() + 'p1'])
    mkfs_root = subprocess.check_output(['sudo', '/sbin/mkfs.ext4', lodevice.strip() + 'p2'])
    subprocess.check_output(['/usr/bin/sudo', '/bin/mkdir', rootfs_dir])
    print('mounting rootfs {} to {}'.format(lodevice + 'p2', rootfs_dir))

    mount_boot = subprocess.check_output(['/usr/bin/sudo', 'mount', lodevice.strip() + 'p2', rootfs_dir])
    subprocess.check_output(['/usr/bin/sudo', '/bin/mkdir', boot_dir])
    print('mounting boot {} to {}'.format(lodevice + 'p1', boot_dir))
    mount_boot = subprocess.check_output(['/usr/bin/sudo', 'mount', lodevice.strip() + 'p1', boot_dir])
    # mount cache dir
    print('mounting cache to {}'.format(rootfs_dir + '/var/cache/dnf'))
    mkdir_tmpfs = subprocess.check_output(['/usr/bin/sudo', '/bin/mkdir', '-p', rootfs_dir + '/var/cache/dnf'])
    mkdir_tmpfs = subprocess.check_output(['/usr/bin/sudo', 'mount', '-t', 'tmpfs', 'none', rootfs_dir + '/var/cache/dnf'])


def find_repos(release, arch):
    url = 'http://abf-downloads.openmandriva.org/{}/repository/{}/main/release/'.format(release, arch)
    resp = requests.get(url)
    if resp.status_code == 404:
        print('bad url: {}'.format(url))
    repo_file = re.search(
        '(?<=href=")openmandriva-repos-.*.aarch64.rpm(?=")', resp.text)
    subprocess.check_output(['/usr/bin/wget', url + repo_file.group(0)])
    return repo_file.group(0)


def make_chroot(release, arch):
    repo_pkg = find_repos(release, arch)
    pkgs = 'NetworkManager less vim-enhanced systemd-console systemd-coredump systemd-cryptsetup systemd-analyze systemd-hwdb systemd-polkit systemd-boot psmisc gptfdisk timezone dnf sudo usbutils passwd kernel-rpi3 kernel-rpi3-modules locales-en kernel-firmware'
    print(rootfs_dir)
    subprocess.check_output(['/usr/bin/sudo', 'rpm', '-Uvh', '--ignorearch', '--nodeps', repo_pkg, '--root', rootfs_dir])
    subprocess.check_output(['/usr/bin/sudo', 'dnf', '-y', 'install', '--nogpgcheck', '--installroot=' + rootfs_dir, '--releasever=' + release, '--forcearch=' + arch] + pkgs.split())
    # copy fstab
    subprocess.check_output(['/usr/bin/sudo', 'cp', '-fv', 'fstab.template', rootfs_dir + '/etc/fstab'])
    # add password 'omv' with precreated hash
    # perl -e 'print crypt($ARGV[0], "password")' omv
    subprocess.check_output(['/usr/bin/sudo', 'useradd', '--prefix', rootfs_dir, 'omv', '-p', 'paknwSLF/t39I', '-G', 'wheel', '-m'])
    umount_tmpfs = subprocess.check_output(['/usr/bin/sudo', 'umount', rootfs_dir + '/var/cache/dnf'])
    umount_boot = subprocess.check_output(['/usr/bin/sudo', 'umount', boot_dir])
    umount_root = subprocess.check_output(['/usr/bin/sudo', 'umount', rootfs_dir])

prepare_rpi_disk()
make_chroot('cooker', 'aarch64')
