//
//    Copyright (C) 2013 - 2020 Hong Jen Yee (PCMan) <pcman.tw@gmail.com>
//
//    This library is free software; you can redistribute it and/or
//    modify it under the terms of the GNU Library General Public
//    License as published by the Free Software Foundation; either
//    version 2 of the License, or (at your option) any later version.
//
//    This library is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//    Library General Public License for more details.
//
//    You should have received a copy of the GNU Library General Public
//    License along with this library; if not, write to the
//    Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
//    Boston, MA  02110-1301, USA.
//

#include "CandidateWindow.h"
#include "DrawUtils.h"
#include "TextService.h"
#include "EditSession.h"

#include <algorithm>
#include <cassert>

#include <tchar.h>
#include <windows.h>

using namespace std;

namespace Ime {

// Win11-style light theme colors
static const COLORREF kBgColor      = RGB(0xFF, 0xFF, 0xFF);
static const COLORREF kBorderColor  = RGB(0xE0, 0xE0, 0xE0);
static const COLORREF kTextColor    = RGB(0x1B, 0x1B, 0x1B);
static const COLORREF kSelKeyColor  = RGB(0x6D, 0x6D, 0x6D);
static const COLORREF kSelBgColor   = RGB(0xE5, 0xE5, 0xE5);  // subtle gray like MS IME
static const COLORREF kSelTextColor = RGB(0x1B, 0x1B, 0x1B);
static const int kCornerRadius = 8;

CandidateWindow::CandidateWindow(TextService* service, EditSession* session):
    ImeWindow(service),
    shown_(false),
    candPerRow_(1),
    textWidth_(0),
    itemHeight_(0),
    currentSel_(0),
    hasResult_(false),
    useCursor_(true),
    selKeyWidth_(0) {

    // horizontal layout, compact padding
    margin_ = 6;
    rowSpacing_ = 2;
    colSpacing_ = 2;
    itemPadX_ = 10;
    itemPadY_ = 5;

    HWND parent = service->compositionWindow(session);
    // render at physical pixels even in DPI-unaware host apps (sharp text)
    DPI_AWARENESS_CONTEXT prevCtx =
        SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    create(parent, WS_POPUP|WS_CLIPCHILDREN, WS_EX_TOOLWINDOW|WS_EX_TOPMOST);
    SetThreadDpiAwarenessContext(prevCtx);
}

CandidateWindow::~CandidateWindow(void) {
}

// ITfUIElement
STDMETHODIMP CandidateWindow::GetDescription(BSTR *pbstrDescription) {
    if (!pbstrDescription)
        return E_INVALIDARG;
    *pbstrDescription = SysAllocString(L"Candidate window~");
    return S_OK;
}

// {BD7CCC94-57CD-41D3-A789-AF47890CEB29}
STDMETHODIMP CandidateWindow::GetGUID(GUID *pguid) {
    if (!pguid)
        return E_INVALIDARG;
    *pguid = { 0xbd7ccc94, 0x57cd, 0x41d3, { 0xa7, 0x89, 0xaf, 0x47, 0x89, 0xc, 0xeb, 0x29 } };
    return S_OK;
}

STDMETHODIMP CandidateWindow::Show(BOOL bShow) {
    shown_ = bShow;
    if (shown_)
        show();
    else
        hide();
    return S_OK;
}

STDMETHODIMP CandidateWindow::IsShown(BOOL *pbShow) {
    if (!pbShow)
        return E_INVALIDARG;
    *pbShow = shown_;
    return S_OK;
}

// ITfCandidateListUIElement
STDMETHODIMP CandidateWindow::GetUpdatedFlags(DWORD *pdwFlags) {
    if (!pdwFlags)
        return E_INVALIDARG;
    /// XXX update all!!!
    *pdwFlags = TF_CLUIE_DOCUMENTMGR | TF_CLUIE_COUNT | TF_CLUIE_SELECTION | TF_CLUIE_STRING | TF_CLUIE_PAGEINDEX | TF_CLUIE_CURRENTPAGE;
    return S_OK;
}

STDMETHODIMP CandidateWindow::GetDocumentMgr(ITfDocumentMgr **ppdim) {
    if (!textService_)
        return E_FAIL;
    return textService_->currentContext()->GetDocumentMgr(ppdim);
}

STDMETHODIMP CandidateWindow::GetCount(UINT *puCount) {
    if (!puCount)
        return E_INVALIDARG;
    *puCount = std::min<UINT>(10, items_.size());
    return S_OK;
}

STDMETHODIMP CandidateWindow::GetSelection(UINT *puIndex) {
    assert(currentSel_ >= 0);
    if (!puIndex)
        return E_INVALIDARG;
    *puIndex = static_cast<UINT>(currentSel_);
    return S_OK;
}

STDMETHODIMP CandidateWindow::GetString(UINT uIndex, BSTR *pbstr) {
    if (!pbstr)
        return E_INVALIDARG;
    if (uIndex >= items_.size())
        return E_INVALIDARG;
    *pbstr = SysAllocString(items_[uIndex].c_str());
    return S_OK;
}

STDMETHODIMP CandidateWindow::GetPageIndex(UINT *puIndex, UINT uSize, UINT *puPageCnt) {
    /// XXX Always return the same single page index.
    if (!puPageCnt)
        return E_INVALIDARG;
    *puPageCnt = 1;
    if (puIndex) {
        if (uSize < *puPageCnt) {
            return E_INVALIDARG;
        }
        puIndex[0] = 0;
    }
    return S_OK;
}

STDMETHODIMP CandidateWindow::SetPageIndex(UINT *puIndex, UINT uPageCnt) {
    /// XXX Do not let app set page indices.
    if (!puIndex)
        return E_INVALIDARG;
    return S_OK;
}

STDMETHODIMP CandidateWindow::GetCurrentPage(UINT *puPage) {
    if (!puPage)
        return E_INVALIDARG;
    *puPage = 0;
    return S_OK;
}

LRESULT CandidateWindow::wndProc(UINT msg, WPARAM wp , LPARAM lp) {
    switch (msg) {
        case WM_PAINT:
            onPaint(wp, lp);
            break;
        case WM_ERASEBKGND:
            return TRUE;
            break;
        case WM_LBUTTONDOWN:
            onLButtonDown(wp, lp);
            break;
        case WM_MOUSEMOVE:
            onMouseMove(wp, lp);
            break;
        case WM_LBUTTONUP:
            onLButtonUp(wp, lp);
            break;
        case WM_MOUSEACTIVATE:
            return MA_NOACTIVATE;
        default:
            return Window::wndProc(msg, wp, lp);
    }
    return 0;
}

void CandidateWindow::onPaint(WPARAM wp, LPARAM lp) {
    // modern paint: white bg, rounded light border, blue pill highlight
    PAINTSTRUCT ps;
    BeginPaint(hwnd_, &ps);
    HDC hDC = ps.hdc;
    HFONT oldFont;
    RECT rc;

    oldFont = (HFONT)SelectObject(hDC, font_);

    GetClientRect(hwnd_,&rc);
    SetTextColor(hDC, kTextColor);
    SetBkColor(hDC, kBgColor);
    SetBkMode(hDC, TRANSPARENT);  // transparent text bg, or it covers the highlight pill

    // paint window background and border
    ::FillSolidRect(ps.hdc, rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top, kBgColor);
    {
        HPEN pen = ::CreatePen(PS_SOLID, 1, kBorderColor);
        HGDIOBJ oldPen = ::SelectObject(hDC, pen);
        HGDIOBJ oldBrush = ::SelectObject(hDC, ::GetStockObject(NULL_BRUSH));
        ::RoundRect(hDC, rc.left, rc.top, rc.right - 1, rc.bottom - 1,
                    kCornerRadius * 2, kCornerRadius * 2);
        ::SelectObject(hDC, oldBrush);
        ::SelectObject(hDC, oldPen);
        ::DeleteObject(pen);
    }

    // paint items
    int col = 0;
    int x = margin_, y = margin_;
    for(int i = 0, n = items_.size(); i < n; ++i) {
        paintItem(hDC, i, x, y);
        ++col; // go to next column
        if(col >= candPerRow_) {
            col = 0;
            x = margin_;
            y += itemHeight_ + rowSpacing_;
        }
        else {
            x += colSpacing_ + selKeyWidth_ + textWidth_ + itemPadX_ * 2;
        }
    }
    SelectObject(hDC, oldFont);
    EndPaint(hwnd_, &ps);
}

void CandidateWindow::recalculateSize() {
    if(items_.empty()) {
        resize(margin_ * 2, margin_ * 2);
    }

    HDC hDC = ::GetWindowDC(hwnd());
    int height = 0;
    int width = 0;
    selKeyWidth_ = 0;
    textWidth_ = 0;
    itemHeight_ = 0;

    HGDIOBJ oldFont = ::SelectObject(hDC, font_);
    vector<wstring>::const_iterator it;
    for(int i = 0, n = items_.size(); i < n; ++i) {
        SIZE selKeySize;
        int lineHeight = 0;
        // the selection key string
        wchar_t selKey[] = L"?. ";
        selKey[0] = selKeys_[i];
        ::GetTextExtentPoint32W(hDC, selKey, 3, &selKeySize);
        if(selKeySize.cx > selKeyWidth_)
            selKeyWidth_ = selKeySize.cx;

        // the candidate string
        SIZE candidateSize;
        wstring& item = items_.at(i);
        ::GetTextExtentPoint32W(hDC, item.c_str(), item.length(), &candidateSize);
        if(candidateSize.cx > textWidth_)
            textWidth_ = candidateSize.cx;
        int itemHeight = max(candidateSize.cy, selKeySize.cy);
        if(itemHeight > itemHeight_)
            itemHeight_ = itemHeight;
    }
    ::SelectObject(hDC, oldFont);
    ::ReleaseDC(hwnd(), hDC);
    itemHeight_ += itemPadY_ * 2;  // vertical padding inside a row

    if(items_.size() <= candPerRow_) {
        width = items_.size() * (selKeyWidth_ + textWidth_ + itemPadX_ * 2);
        width += colSpacing_ * (items_.size() - 1);
        width += margin_ * 2;
        height = itemHeight_ + margin_ * 2;
    }
    else {
        width = candPerRow_ * (selKeyWidth_ + textWidth_ + itemPadX_ * 2);
        width += colSpacing_ * (candPerRow_ - 1);
        width += margin_ * 2;
        int rowCount = items_.size() / candPerRow_;
        if(items_.size() % candPerRow_)
            ++rowCount;
        height = itemHeight_ * rowCount + rowSpacing_ * (rowCount - 1) + margin_ * 2;
    }
    resize(width, height);

    // rounded window: clip with a round-rect region
    if(HRGN rgn = ::CreateRoundRectRgn(0, 0, width + 1, height + 1,
                                       kCornerRadius * 2, kCornerRadius * 2))
        ::SetWindowRgn(hwnd(), rgn, TRUE);  // system owns the rgn, do NOT DeleteObject
}

void CandidateWindow::setCandPerRow(int n) {
    if(n != candPerRow_) {
        candPerRow_ = n;
        recalculateSize();
    }
}

bool CandidateWindow::filterKeyEvent(KeyEvent& keyEvent) {
    // select item with arrow keys
    int oldSel = currentSel_;
    switch(keyEvent.keyCode()) {
    case VK_UP:
        if(currentSel_ - candPerRow_ >=0)
            currentSel_ -= candPerRow_;
        break;
    case VK_DOWN:
        if(currentSel_ + candPerRow_ < items_.size())
            currentSel_ += candPerRow_;
        break;
    case VK_LEFT:
        if(currentSel_ - 1 >=0)
            --currentSel_;
        break;
    case VK_RIGHT:
        if(currentSel_ + 1 < items_.size())
            ++currentSel_;
        break;
    case VK_RETURN:
        hasResult_ = true;
        return true;
    default:
        return false;
    }
    // if currently selected item is changed, redraw
    if(currentSel_ != oldSel) {
        // repaint the old and new items
        RECT rect;
        itemRect(oldSel, rect);
        ::InvalidateRect(hwnd_, &rect, TRUE);
        itemRect(currentSel_, rect);
        ::InvalidateRect(hwnd_, &rect, TRUE);
        return true;
    }
    return false;
}

void CandidateWindow::setCurrentSel(int sel) {
    if(sel >= items_.size())
        sel = 0;
    if (currentSel_ != sel) {
        currentSel_ = sel;
        if (isVisible())
            ::InvalidateRect(hwnd_, NULL, TRUE);
    }
}

void CandidateWindow::clear() {
    items_.clear();
    selKeys_.clear();
    currentSel_ = 0;
    hasResult_ = false;
}

void CandidateWindow::setUseCursor(bool use) {
    useCursor_ = use;
    if(isVisible())
        ::InvalidateRect(hwnd_, NULL, TRUE);
}

void CandidateWindow::paintItem(HDC hDC, int i,  int x, int y) {
    bool selected = (useCursor_ && i == currentSel_);
    int cellWidth = selKeyWidth_ + textWidth_ + itemPadX_ * 2;

    // selected item: blue rounded highlight pill
    if(selected) {
        HBRUSH brush = ::CreateSolidBrush(kSelBgColor);
        HGDIOBJ oldBrush = ::SelectObject(hDC, brush);
        HGDIOBJ oldPen = ::SelectObject(hDC, ::GetStockObject(NULL_PEN));
        ::RoundRect(hDC, x, y, x + cellWidth, y + itemHeight_,
                    kCornerRadius, kCornerRadius);
        ::SelectObject(hDC, oldPen);
        ::SelectObject(hDC, oldBrush);
        ::DeleteObject(brush);
    }

    int tx = x + itemPadX_;
    int ty = y + itemPadY_;
    RECT textRect = {tx, ty, 0, ty + itemHeight_ - itemPadY_ * 2};
    wchar_t selKey[] = L"?. ";
    selKey[0] = selKeys_[i];
    textRect.right = textRect.left + selKeyWidth_;

    // paint the selection key
    ::SetTextColor(hDC, selected ? kSelTextColor : kSelKeyColor);
    ::ExtTextOut(hDC, textRect.left, textRect.top, 0, NULL, selKey, 3, NULL);

    // paint the candidate string
    wstring& item = items_.at(i);
    textRect.left += selKeyWidth_;
    textRect.right = textRect.left + textWidth_;
    ::SetTextColor(hDC, selected ? kSelTextColor : kTextColor);
    ::ExtTextOut(hDC, textRect.left, textRect.top, 0, NULL, item.c_str(), item.length(), NULL);
}

void CandidateWindow::itemRect(int i, RECT& rect) {
    int row, col;
    row = i / candPerRow_;
    col = i % candPerRow_;
    rect.left = margin_ + col * (selKeyWidth_ + textWidth_ + itemPadX_ * 2 + colSpacing_);
    rect.top = margin_ + row * (itemHeight_ + rowSpacing_);
    rect.right = rect.left + (selKeyWidth_ + textWidth_ + itemPadX_ * 2);
    rect.bottom = rect.top + itemHeight_;
}


} // namespace Ime
