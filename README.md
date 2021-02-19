# pyqt5-gui-prototype

## Installing PyQt5 for python 2.7 on Centos/RHEL 7

Create a python 2.7 environment if not existing:

```
bash-4.2$ pyenv install 2.7.5
bash-4.2$ pyenv virtualenv 2.7.5 bmit27
```

Activate your environment and install enum34
```
bash-4.2$ pyenv activate bmit27
(bmit27) bash-4.2$ pip install enum34
```

Download and install (in your environment!!!) SIP
```
wget https://www.riverbankcomputing.com/static/Downloads/sip/4.19.14/sip-4.19.14.tar.gz
tar -xvf sip-4.19.14.tar.gz 
cd sip-4.19.14
python configure.py --sip-module=PyQt5.sip
make -j 4
make install
```

Download and install (in your environment!!!) compatible version of PyQt5
```
wget https://www.riverbankcomputing.com/static/Downloads/PyQt5/5.12/PyQt5_gpl-5.12.tar.gz
tar -xvf PyQt5_gpl-5.12.tar.gz 
cd PyQt5_gpl-5.12
python configure.py --confirm-license --disable=QtNfc --qmake=/usr/lib64/qt5/bin/qmake QMAKE_LFLAGS_RPATH=
make -j 4
make install
```

Check installation with `pip list`

### Building styles:
in project directory run:
```
cd ./styles/breeze/
pyrcc5 breeze.qrc -o styles_breeze.py
```
